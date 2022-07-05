import smtplib

from django.shortcuts import render, redirect
import re
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.views import View
from django.urls import reverse
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings
from itsdangerous import TimedSerializer
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_register_active_email

User = get_user_model()


class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        password2 = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # verify
        # data incomplete
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': 'data incomplete'})
        # email
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': 'email form illegal'})

        # psw
        if not password == password2:
            return render(request, 'register.html', {'errmsg': 'password non correspondent'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': 'non accept contract'})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # user non exist
            user = None
        # user exist
        if user:
            print('===user exist===')
            return render(request, 'register.html', {'errmsg': 'user exist'})

        user = User.objects.create_user(username, email, password)
        user.is_active = 1 # During the send email no work user.is_active = 0
        user.save()

        # activity login
        # mask user ID by itsdangerous
        # Time out 3600s = 1 hour
        serializer = TimedSerializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        # token = str(b'serializer.dumps(info)', "utf-8")
        token = serializer.dumps(info)
        token = token.decode("utf-8")

        # send pre user email

        # subject = 'Dailyfresh welcome new client'
        # message = ''
        # sender = settings.EMAIL_FROM
        # receiver = [User.email]
        #
        # html_message = '<h1>%s, Dailyfresh' \
        #                '</h1>Please click the link below to active your count<br/>' \
        #                '<a href="http://127.0.0.1:8000/user/active/%s">' \
        #                'http://127.0.0.1:8000/user/active/%s' \
        #                '</a>' % (username, token, token)
        #
        # server = smtplib.SMTP('smtp.gmail.com', 587)
        # server.ehlo()
        # server.starttls()
        # server.ehlo()
        # server.login("Wj19930703@gmail.com", "Average101")
        #
        # # send_mail(subject, message, sender, receiver, html_message=html_message)
        # server.sendmail(sender, receiver, html_message)
        # server.quit()
        send_register_active_email.delay(email, username, token)
        return redirect(reverse('index'))

class ActiveView(View):
    def get(self, request, token):
        serializer = TimedSerializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.load(token)
            # get user id
            user_id = info['confirm']
            # get user
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # redirect to login
            return redirect(reverse('login'))
        except SignatureExpired as err:
            # Secret key is time out
            return HttpResponse('Secret key is time out')


class LoginView(View):
    def get(self, request):
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': 'non complete'})

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                response = redirect(reverse('index'))
                remember = request.POST.get('remember')

                if remember == 'on':
                    response.set_cookie('username', username, max_age=7*24*3600) # one week
                else:
                    response.delete_cookie('username')
                # print("User is valid, active and authenticated.")
                return response
            else:
                # print("The password is valid, but the account has been disabled.")
                return render(request, 'login.html', {'errmsg': 'account has been disabled.'})
        else:
            # print("The username or password were incorrect.")
            return render(request, 'login.html', {'errmsg': 'username or password were incorrect.'})

class UserInfoView(View):
    def get(self, request):
        return render(request, 'user_center_info.html')

class UserOrderView(View):
    def get(self, request):
        return render(request, 'user_center_order.html')

class AddressView(View):
    def get(self, request):
        return render(request, 'user_center_site.html')

class LogoutView(View):
    """退出登录"""
    def get(self, request):
        # logout(request)

        return redirect(reverse('goods:index'))