from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from home.models import ArticleCategory, Ariticle, Comment
from django.core.paginator import Paginator, EmptyPage
from django.http.response import HttpResponseNotFound

# Create your views here.


# 首页视图
class IndexView(View):
    @staticmethod
    def get(request):
        """
        1.获取所有分类信息
        2.接收用户点击的分类id
        3.根据分类id进行分类的查询
        4.获取分页参数
        5.根据分类信息查询文章数据
        6.创建分页器
        7.进行分页处理
        8.组织数据传递给模板
        :param request:
        :return:
        """
        # 1.获取所有分类信息
        categories = ArticleCategory.objects.all()
        # 2.接收用户点击的分类id
        cat_id = request.GET.get('cat_id', 1)
        # 3.根据分类id进行分类的查询
        try:
            category = ArticleCategory.objects.get(id=cat_id)
        except ArticleCategory.DoesNotExist:
            return HttpResponseNotFound('没有此分类')
        # 4.获取分页参数
        page_num = request.GET.get('page_num', 1)
        page_size = request.GET.get('page_size', 10)
        # 5.根据分类信息查询文章数据
        articles = Ariticle.objects.filter(category=category)
        # 6.创建分页器
        paginator = Paginator(articles, per_page=page_size)
        # 7.进行分页处理
        try:
            page_articles = paginator.page(page_num)
        except EmptyPage:
            return HttpResponseNotFound('empty page')
        # 总页数
        total_page = paginator.num_pages

        # 8.组织数据传递给模板
        context = {
            'categories': categories,
            'category': category,
            'articles': page_articles,
            'page_size': page_size,
            'total_page': total_page,
            'page_num': page_num
        }
        return render(request, 'index.html', context=context)


class DetailView(View):
    @staticmethod
    def get(request):
        # detail/?id=xxx&page_num=xxx&page_size=xxx
        # 获取文档id
        id = request.GET.get('id')
        page_num = request.GET.get('page_num', 1)
        page_size = request.GET.get('page_size', 5)

        # 获取博客分类信息
        categories = ArticleCategory.objects.all()

        # 获取热点数据
        hot_articles = Ariticle.objects.order_by('-total_views')[:9]

        try:
            article = Ariticle.objects.get(id=id)
        except Ariticle.DoesNotExist:
            return render(request, '404.html')
        else:
            article.total_views += 1
            article.save()

        # 获取当前文章的评论数据
        comments = Comment.objects.filter(
            article=article
        ).order_by('-created')

        # 获取评论总数
        total_count = comments.count()

        # 创建分页器：每页N条记录
        paginator = Paginator(comments, page_size)

        # 获取每页数据
        try:
            page_comments = paginator.page(page_num)
        except EmptyPage:
            # 如果page不正确，返回404
            return HttpResponseNotFound('empty page')

        # 获取列表页总页数
        total_page = paginator.num_pages

        context = {
            'categories': categories,
            'category': article.category,
            'article': article,
            'hot_articles': hot_articles,
            'total_count': total_count,
            'comments': page_comments,
            'page_size': page_size,
            'total_page': total_page,
            'page_num': page_num,
        }

        return render(request, 'detail.html', context=context)

    @staticmethod
    def post(request):

        # 获取用户信息
        user = request.user

        # 判断用户是否登录
        if user and user.is_authenticated:
            # 接收数据
            id = request.POST.get('id')
            content = request.POST.get('content')

            # 判断文章是否存在
            try:
                article = Ariticle.objects.get(id=id)
            except Ariticle.DoesNotExist:
                return HttpResponseNotFound('没有此文章')

            # 保存数据
            Comment.objects.create(
                content=content,
                article=article,
                user=user
            )

            # 修改文章评论数
            article.comments_count += 1
            article.save()

            # 拼接跳转路由
            path = reverse('home:detail')+'?id={}'.format(article.id)
            return redirect(path)
        else:
            # 没有登录则跳转登录页面
            return redirect(reverse('users:login'))
