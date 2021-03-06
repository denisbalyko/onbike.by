# -*- coding: utf-8 -*-
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotFound
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.template.context import RequestContext
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.utils.datastructures import MultiValueDictKeyError

from account.models import Account, ACCOUNT_BACKENDS
from account.backends import DenyException
#from account.backends.twitter import TwitterBackend
from backends import get_backend

def _error_page(request):
    message = u"Ошибка авторизации! Перейдите по ссылке, чтобы повторить попытку."
    redirect = {'url': reverse('account_login'),
                'title': u"Попробовать еще раз."}
    return render_to_response('account/error_page.html',
                              {'message': message,
                               'redirect': redirect},
                              RequestContext(request))    

def login_page(request):
    #print request.user.is_authenticated()
    backends = []
    for b in ACCOUNT_BACKENDS:
        backends.append({'name': b[0],
                         'title': b[1],
                         'img': '/static/account/img/%s.png' % b[0],
                         'url': reverse('login_start', args=[b[0]])})
    return render_to_response('account/login.html',
                              {'backends': backends},
                              RequestContext(request))

def login_start(request, backend_name):
    backend = get_backend(backend_name)
    if backend is None:
        return HttpResponseNotFound()
    redirect_url = request.META.get('HTTP_REFERER','/')
    print redirect_url
    request.session['post_login_redirect'] = redirect_url
    return_url = "http://%s%s" % (settings.MAIN_HOST,
                                  reverse('login_return', args=[backend_name]))
    token, url = backend.get_auth_url(return_to=return_url)
    request.session['account_token'] = token
    return HttpResponseRedirect(url)

def login_return(request, backend_name):
    backend = get_backend(backend_name)
    redirect_url = request.session.get('post_login_redirect', '/')
    return_url = "http://%s%s" % (settings.MAIN_HOST,
                                  reverse('login_return', args=[backend_name]))
    try:
        access_token = backend.get_token(request, return_url)
    except DenyException:
        return HttpResponseRedirect(redirect_url)
    except:
        return _error_page(request)

    user_data = backend.get_user_data(access_token)
    
    account = Account.objects.filter(id_from_backend=user_data['id'],
                                     backend=backend_name,
                                     )
    if account.count():
        account = account[0]
        user = account.user
        user = authenticate(username=user.username, password=2)
        login(request, user)
        return HttpResponseRedirect(redirect_url)
    if not request.user.is_authenticated():
        un = "%s - %s" % (user_data['screen_name'], user_data['id'])
        un = un[:30]
        user, created = User.objects.get_or_create(username=un)
        if created:
            temp_password = User.objects.make_random_password(length=12)
            user.set_password(temp_password)
        user.first_name = user_data['name']
        user.save()
        user = authenticate(username=user.username, password=2)
    else:
        user = request.user
    account = Account(user=user,
                      name=user.first_name,
                      img_url=user_data['picture'],
                      backend=backend_name,
                      id_from_backend=user_data['id'],
                      ) 
    account.save()
    login(request, user)
    return HttpResponseRedirect(redirect_url)
