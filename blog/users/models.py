from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class User(AbstractUser):
    #   手机号
    #   max_length=11最大长度为11，unique=True唯一，blank=False必须填写
    mobile = models.CharField(max_length=11, unique=True, blank=False)
    #   修改手机为认证字段
    USERNAME_FIELD = 'mobile'
    #   头像
    #   upload_to上传位置, blank=True不必须填写
    avatar = models.ImageField(upload_to='avatar/%Y%m%d/', blank=True)
    #   简介
    user_desc = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'tb_users'   # 修改表名
        verbose_name = '用户管理'   # admin 后台显示
        verbose_name_plural = verbose_name  # admin 后台显示

    def __str__(self):
        return self.mobile
