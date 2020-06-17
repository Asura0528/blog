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
from django.contrib.auth import login
import logging
import re
logger = logging.getLogger('django')


# 注册视图
class RegisterView(View):

    @staticmethod
    def get(request):
        return render(request, 'register.html')

    def post(self, request):
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
