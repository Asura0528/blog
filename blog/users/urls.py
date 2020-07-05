# 进行users 子应用的视图路由from django.urls import pathfrom users.views import RegisterView, ImageCodeView, SmsCodeView, LoginView, LogoutView, ForgetPasswordView, UserCenterView, WriteBlogView, SelfBlogViewurlpatterns = [    # path第一个参数：路由    # path第二个参数：视图函数名    path('register/', RegisterView.as_view(), name='register'),    # 图片验证码路由    path('imagecode/', ImageCodeView.as_view(), name='imagecode'),    # 短信发送路由    path('smscode/', SmsCodeView.as_view(), name='smscode'),    # 登录路由    path('login/', LoginView.as_view(), name='login'),    # 登出路由    path('logout/', LogoutView.as_view(), name='logout'),    # 忘记密码路由    path('forget_password/', ForgetPasswordView.as_view(), name='forgetpassword'),    # 用户中心路由    path('center/', UserCenterView.as_view(), name='center'),    # 写博客路由    path('write_blog/', WriteBlogView.as_view(), name='writeblog'),    # 个人博客路由    path('self_blog/', SelfBlogView.as_view(), name='selfblog')]