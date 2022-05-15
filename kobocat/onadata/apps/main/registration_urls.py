"""
URLConf for Django user registration and authentication.

Recommended usage is a call to ``include()`` in your project's root
URLConf to include this URLConf for any URL beginning with
``/accounts/``.

"""


from django.conf.urls import patterns, url, include
from django.views.generic import TemplateView
from registration.backends.default.views import ActivationView

from onadata.apps.main.registration_views import FHRegistrationView
from onadata.apps.main.forms import RegistrationFormUserProfile

urlpatterns = patterns(
    '',
    url(r'^activate/complete/$',
        TemplateView.as_view(
            template_name='registration/activation_complete.html'),
        name='registration_activation_complete'),
    # Activation keys get matched by \w+ instead of the more specific
    # [a-fA-F0-9]{40} because a bad activation key should still get to the view
    # that way it can return a sensible "invalid key" message instead of a
    # confusing 404.
    url(r'^activate/(?P<activation_key>\w+)/$',
        ActivationView.as_view(),
        name='registration_activate'),
    url(r'^register/$',
        FHRegistrationView.as_view(form_class=RegistrationFormUserProfile),
        name='registration_register'),
    url(r'^register/complete/$',
        TemplateView.as_view(
            template_name='registration/registration_complete.html'),
        name='registration_complete'),
    url(r'^login/$', 'onadata.apps.usermodule.views.user_login', name='user_login'), #mpower add
    url(r'^logout/$', 'onadata.apps.usermodule.views.user_logout', name='user_logout'), #mpower add
    (r'', include('registration.auth_urls')),

)
