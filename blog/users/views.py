from django.shortcuts import render
# Create your views here.
from django.views import View
from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse
from libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from utils.response_code import RETCODE
from random import randint
from libs.yuntongxun.sms import CCP
from users.models import User
from django.db import DatabaseError
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.mixins import LoginRequiredMixin
import logging
import re

logger = logging.getLogger('django')


# 注册视图
class RegisterView(View):

    @staticmethod
    def get(request):
        return render(request, 'register.html')

    @staticmethod
    def post(request):
        """
        1、接收参数
        2、验证参数
            2.1 参数是否齐全
            2.2 手机号格式是否正确
            2.3 密码格式是否正确
            2.4 密码和确认密码要一致
            2.5 短信验证码是否和redis中的一致
        3、保存注册信息
        4、返回跳转页面
        :param request:
        :return:
        """
        # 1、接收参数
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode = request.POST.get('sms_code')
        # 2、验证参数
        #     2.1 参数是否齐全
        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest('缺少必要的参数')
        #     2.2 手机号格式是否正确
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('手机号不符合规则')
        #     2.3 密码格式是否正确
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest('请输入8-20位密码，密码可以是数字，字母')
        #     2.4 密码和确认密码要一致
        if password != password2:
            return HttpResponseBadRequest('两次密码不一致')
        #     2.5 短信验证码是否和redis中的一致
        redis_conn = get_redis_connection('default')
        redis_sms_code = redis_conn.get('sms:%s' % mobile)
        if redis_sms_code is None:
            return HttpResponseBadRequest('短信验证码已过期')
        if smscode != redis_sms_code.decode():
            return HttpResponseBadRequest('短信验证码不一致')
        # 3、保存注册信息
        # creat_user 可以使用系统的方法对密码进行加密，使用try创建加密用户
        try:
           user = User.objects.create_user(username=mobile,
                                           mobile=mobile,
                                           password=password)
        except DatabaseError as e:
            logger(e)
            return HttpResponseBadRequest('注册失败')
        # 状态保持
        login(request, user)
        # 4、返回跳转页面
        # 暂时返回一个注册成功的信息，后期再实现跳转到指定页面
        # redirect 是重定向
        # reverse 是可以通过namespace:name 来获取到视图所对应的路由
        response = redirect(reverse('home:index'))
        # return HttpResponse('注册成功，重定向到首页')

        # 设置cookie信息，以方便首页中，用户信息展示的判断和用户信息的展示
        response.set_cookie('is_login', True)
        response.set_cookie('username', user.username, max_age=7*24*3600)

        return response


# 图片验证码视图
class ImageCodeView(View):

    @staticmethod
    def get(request):
        """
        1.传递前端传递过来的uuid
        2.判断uuid是否获取成功
        3.通过调用captcha生成图片验证码（图片二进制和图片内容）
        4.将 图片内容 保存到redis中
            uuid作为一个key，图片内容作为一个value，同时要设置一个时效
        5.返回图片二进制
        :param request:
        :return:
        """
    # 1.传递前端传递过来的uuid
        uuid = request.GET.get('uuid')
    # 2.判断uuid是否获取成功
        if uuid is None:
            return HttpResponseBadRequest('没有传递uuid')
    # 3.通过调用captcha生成图片验证码（图片二进制和图片内容）
    #         captcha返回text和图片的二进制，使用text和image进行接收
        text, image = captcha.generate_captcha()
    # 4.将 图片内容 保存到redis中
    #       uuid作为一个key，图片内容作为一个value，同时要设置一个时效
        redis_conn = get_redis_connection('default')
        # key 设置为uuid
        # second 过期秒数 300秒 5分钟过期时间
        # value text
        redis_conn.setex('img:%s' % uuid, 300, text)
    # 5.返回图片二进制
        return HttpResponse(image, content_type='image/jpeg')


# 短信验证码视图
class SmsCodeView(View):

    @staticmethod
    def get(request):
        """
        1.接收参数
        2.参数的验证
            2.1 验证参数是否齐全
            2.2 图片验证码的验证
                链接redis，获取redis中的图片验证码
                判断图片验证码是否存在
                如果图片验证码未过期，我们获取到之后就可以删除图片验证码
                比对图片验证码（不分大小写）
        3.生成短信验证码
        4.保存短信验证码到redis中
        5.发送短信
        6.返回响应
        :param request:
        :return:
        """

        # 1.接收参数
        mobile = request.GET.get('mobile')
        image_code = request.GET.get('image_code')
        uuid = request.GET.get('uuid')
        # 2.参数的验证
        #   2.1验证参数是否齐全
        if not all([mobile, image_code, uuid]):
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '缺少必要的参数'})
        #   2.2图片验证码的验证
        #       链接redis，获取redis中的图片验证码
        redis_conn = get_redis_connection('default')
        redis_image_code = redis_conn.get('img:%s' % uuid)
        #       判断图片验证码是否存在
        if redis_image_code is None:
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码已过期'})
        #       如果图片验证码未过期，我们获取到之后就可以删除图片验证码
        try:
            redis_conn.delete('img:%s' % uuid)
        except Exception as e:
            logger.error(e)
        #       比对图片验证码（不分大小写），redis的数据时bytes类型
        if redis_image_code.decode().lower() != image_code.lower():
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码错误'})
        # 3.生成短信验证码
        sms_code = '%06d' % randint(0, 999999)
        # 为了后期比对方便，将短信验证码记录到日志中
        logger.info(sms_code)
        # 4.保存短信验证码到redis中
        redis_conn.setex('sms:%s' % mobile, 300, sms_code)
        # 5.发送短信
        # 参数1：测试手机号
        # 参数2（列表）：您的验证码是{1}，请于{2}分钟内正确输入
        #   {1} 短信验证码
        #   {2} 短信验证码有效期
        # 参数3：免费开发测试使用的模板ID为1
        CCP().send_template_sms(mobile, [sms_code, 5], 1)
        # 6.返回响应
        return JsonResponse({'code': RETCODE.OK, 'errmsg': '短信发送成功'})


# 登录视图
class LoginView(View):

    @staticmethod
    def get(request):
        return render(request, 'login.html')

    @staticmethod
    def post(request):
        """
        1.接收参数
        2.参数的验证
            2.1 验证手机号是否符合规则
            2.2 验证密码是否符合规则
        3.用户认证登录
        4.状态的保持
        5.根据用户选择的是否记住登录状态来进行判断
        6.为了首页显示我们需要设置一些cookie信息
        7.返回响应
        :param request:
        :return:
        """
        # 1.接收参数
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        # 2.参数的验证
        #     2.1 验证手机号是否符合规则
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('手机号不符合规则')
        #     2.2 验证密码是否符合规则
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return HttpResponseBadRequest('密码不符合规则')
        # 3.用户认证登录
        # 采用系统自带的认证方法进行认证
        # 如果我们的用户名和密码正确，会返回user
        # 如果我们的用户名或密码不正确，会返回None
        # 默认的认证方法是针对于 username 字段进行用户名的判断
        # 当前的判断信息是手机号所以我们需要修改一下认证字段
        # 我们需要到User模型中进行修改，等测试出现问题的时候，我们再修改
        user = authenticate(mobile=mobile, password=password)
        if user is None:
            return HttpResponseBadRequest('用户名或密码错误')
        # 4.状态的保持
        login(request, user)
        # 5.根据用户选择的是否记住登录状态来进行判断
        # 6.为了首页显示我们需要设置一些cookie信息
        # 根据next参数来进行页面的跳转
        next_page = request.GET.get('next')
        if next_page:
            response = redirect(next_page)
        else:
            response = redirect(reverse('home:index'))
        if remember != 'on':    # 没有记住用户信息
            # 浏览器关闭之后
            request.session.set_expiry(0)
            response.set_cookie('is_login', True)
            response.set_cookie('username', user.username, max_age=14*24*3600)
        else:                   # 记住用户信息
            # 默认是记住 2周
            request.session.set_expiry(None)
            # 设置cookie
            response.set_cookie('is_login', True, max_age=14*24*3600)
            response.set_cookie('username', user.username, max_age=14*24*3600)
        # 7.返回响应
        return response


# 登出视图
class LogoutView(View):

    @staticmethod
    def get(request):
        # 清理session
        logout(request)
        # 退出登录，重定向到登录页
        response = redirect(reverse('home:index'))
        # 退出登录时，删除cookie状态
        response.delete_cookie('is_login')
        return response


# 忘记密码视图
class ForgetPasswordView(View):

    @staticmethod
    def get(request):
        return render(request, 'forget_password.html')

    @staticmethod
    def post(request):
        # 接收参数
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode = request.POST.get('sms_code')

        # 判断参数是否齐全
        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest('缺少必要的参数')

        # 判断手机号码是否符合规则
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('请输入正确手机号')

        # 判断密码是否符合规则（8-20位）
        if not re.match(r'^[0-9a-zA-Z]{8,20}$', password):
            return HttpResponseBadRequest('请输入8-20位密码')

        # 判断密码是否一致
        if password != password2:
            return HttpResponseBadRequest('两次输入的密码不一致')

        # 验证短信验证码
        redis_conn = get_redis_connection('default')
        sms_code_server = redis_conn.get('sms:%s' % mobile)
        # 如果redis库中找不到
        if sms_code_server is None:
            return HttpResponseBadRequest('短信验证码已过期')
        # 如果输入的验证码和redis库中的验证码不一致
        if smscode != sms_code_server.decode():
            return HttpResponseBadRequest('短信验证码错误')

        # 根据手机号查询数据
        try:
            user = User.objects.get(mobile=mobile)
        # 如果手机号不存在
        except User.DoesNotExist():
            return HttpResponseBadRequest('修改失败，手机不存在')
        # 如果手机号存在
        else:
            user.set_password(password)
            user.save()

        # 返回响应
        response = redirect(reverse('users:login'))
        return response


# 用户中心视图
# LoginRequiredMixin
# 如果用户未登录，则会进行默认跳转
# 默认的跳转连接是：accounts/login/?next=xxx
class UserCenterView(LoginRequiredMixin, View):

    @staticmethod
    def get(response):
        return render(response, 'center.html')
