import json
from django import http
from cms import sitemaps
from django.core import mail
from django.conf import settings
from django.views.generic import edit as edit_views
from cmsplugin_dog import models as dog_models
import models
import forms


def _update_user_subscriptions(user, subscribe):
    import mailchimp
    from mailchimp import chimp
    user.subscribed = subscribe
    mailchimp_list = mailchimp.utils.get_connection().get_list_by_id(settings.MAILCHIMP_LIST_ID)
    if subscribe:
        try:
            mailchimp_list.subscribe(user.auth_user.email, { 'EMAIL': user.auth_user.email, 'FNAME': user.auth_user.first_name, })
        except chimp.ChimpyException:
            pass
    else:
        try:
            mailchimp_list.unsubscribe(user.auth_user.email)
        except chimp.ChimpyException:
            pass


class Claim(edit_views.FormView):
    form_class = forms.ClaimForm
    template_name = 'claim.html'

    def get_context_data(self, *args, **kwargs):
        context = super(Claim, self).get_context_data(*args, **kwargs)
        context['dog'] = getattr(self, 'dog', None)
        return context

    def get_initial(self):
        initial = super(Claim, self).get_initial()
        initial.update(forms.ClaimForm.get_initial(self.request.user))
        return initial

    def get_success_url(self):
        return self.dog.get_url()

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        self.dog = self.get_dog(form)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_dog(self, form):
        try:
            return dog_models.Dog.objects.get(pk=form.data['dog'])
        except dog_models.Dog.DoesNotExist:
            raise http.Http404()

    def form_valid(self, form):
        auth_user = self.request.user
        if auth_user.is_authenticated() and auth_user.email == form.cleaned_data['email'].lower():
            try:
                user = auth_user.kapustkinpitomnik_user
            except models.User.DoesNotExist:
                user = None
        else:
            auth_user = auth.authenticate(form.cleaned_data['email'], settings.ANY_PASSWORD)
            if auth_user:
                try:
                    user = auth_user.kapustkinpitomnik_user
                except models.User.DoesNotExist:
                    user = None
            else:
                auth_user = auth.create_user(form.cleaned_data['email'].lower(), settings.ANY_PASSWORD)
                user = None
            auth.login(self.request, auth_user)
        auth_user.first_name = form.cleaned_data['name']
        auth_user.save()
        if user is None:
            user = models.User(
                auth_user=auth_user,
            )
        user.phone = form.cleaned_data['phone']
        _update_user_subscriptions(user, form.cleaned_data['subscribe'])
        user.save()
        subject_dict = {
            'name': auth_user.first_name,
            'dog': self.dog.get_name(),
        }
        if 'for_breeding' == self.dog.status:
            subject_dict['action'] = 'breed with'
        elif 'fertile' == self.dog.status:
            subject_dict['action'] = 'take a puppy from'
        else:
            subject_dict['action'] = 'buy'
        mail.mail_managers(
            '%(name)s wants to %(action)s %(dog)s' % subject_dict,
            'Email: %s\nDog\'s page: http://kapustkapust.ru%s\nPhone: %s' % (auth_user.email, self.dog.get_url(), user.phone),
        )
        return self.render_to_response(self.get_context_data(success=True))


class Sitemap(sitemaps.CMSSitemap):
    def items(self):
        pages = super(Sitemap, self).items()
        return pages.exclude(reverse_id='common')
