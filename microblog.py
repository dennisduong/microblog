import json
import logging
import os
import re
import unicodedata
import urllib
from datetime import datetime
from functools import wraps
from logging.handlers import SMTPHandler

import click
from flask import (
    Flask, abort, flash, g, redirect, render_template, request, 
    send_from_directory, session, url_for)
from flask.cli import AppGroup
from markdown import markdown
from peewee import (
    Model, CharField, TextField, DateTimeField, ManyToManyField, BooleanField,
    IntegrityError)
from playhouse.db_url import connect
from playhouse.flask_utils import get_object_or_404
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

app.config.update({
    "SECRET_KEY": os.getenv('SECRET_KEY') or 'shh...',

    "DATABASE_URL": os.getenv('DATABASE_URL') or 'sqlite:///microblog.db',
    
    "AUTH_USERNAME": os.getenv('AUTH_USERNAME') or 'admin',
    "AUTH_PASSWORD": os.getenv('AUTH_PASSWORD') or 'password',

    "BLOG_BRAND": os.getenv('BLOG_BRAND') or 'microblog',
    "BLOG_TITLE": os.getenv('BLOG_TITLE') or 'Microblog',
    "BLOG_DESCRIPTION": (os.getenv('BLOG_DESCRIPTION') or 
                         'A microblog from a developer who does things.'),
    "BLOG_AUTHOR_NAME": os.getenv('BLOG_AUTHOR_NAME') or 'Microblog Inc.',
    "BLOG_AUTHOR_GITHUB": os.getenv('BLOG_AUTHOR_GITHUB'),
    "BLOG_AUTHOR_TWITTER": os.getenv('BLOG_AUTHOR_TWITTER'),

    "PROXYFIX_X_FOR": int(os.getenv("PROXYFIX_X_FOR") or 0),
    "PROXYFIX_X_PROTO": int(os.getenv("PROXYFIX_X_PROTO") or 0),
    "PROXYFIX_X_HOST": int(os.getenv("PROXYFIX_X_HOST") or 0),
    
    "MAIL_SERVER": os.getenv('MAIL_SERVER'),
    "MAIL_PORT": int(os.getenv('MAIL_PORT', 587)),
    "MAIL_USERNAME": os.getenv('MAIL_USERNAME'),
    "MAIL_PASSWORD": os.getenv('MAIL_PASSWORD'),
    "MAIL_USE_TLS": os.getenv('MAIL_USE_TLS') is not None,
    "MAIL_FROMADDR": os.getenv('MAIL_FROMADDR'),
    "MAIL_TOADDRS": json.loads(os.getenv('MAIL_TOADDRS') or '[]'),

    "ANALYTICS_GTAG": os.getenv('ANALYTICS_GTAG'),
})
app.config.from_json('/etc/microblog.json', silent=True)
app.config.from_pyfile('/etc/microblog.conf', silent=True)

cli = AppGroup('manage', help='Manage microblog')
app.cli.add_command(cli)

# If using SQLite, set the "foreign_keys" pragma to ON.
if app.config['DATABASE_URL'].startswith('sqlite'):
    db = connect(app.config['DATABASE_URL'], pragmas={'foreign_keys': 1})
else:
    db = connect(app.config['DATABASE_URL'])

if (
    app.config['PROXYFIX_X_FOR'] or 
    app.config['PROXYFIX_X_PROTO'] or 
    app.config['PROXYFIX_X_HOST']
):
    app = ProxyFix(app, 
                   x_for=app.config['PROXYFIX_X_FOR'], 
                   x_proto=app.config['PROXYFIX_X_PROTO'], 
                   x_host=app.config['PROXYFIX_X_HOST'])


def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.

    https://github.com/django/django/blob/3.1.5/django/utils/text.py#L394
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = (unicodedata
                 .normalize('NFKD', value)
                 .encode('ascii', 'ignore')
                 .decode('ascii'))
    value = re.sub(r'[^\w\s-]', '', value.lower()).strip()
    return re.sub(r'[-\s]+', '-', value)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.authenticated:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


class BaseModel(Model):
    class Meta:
        database = db


class Post(BaseModel):
    title = CharField()
    slug = CharField(unique=True)
    description = CharField()
    content = TextField()
    published = BooleanField(default=False)
    timestamp = DateTimeField(default=datetime.utcnow)

    def get_html(self):
        return markdown('[TOC]\n\n' + self.content, 
                        output_format='html5',
                        extensions=['extra', 'toc', 'codehilite', 'admonition'],
                        extension_configs={
                            'codehilite': {
                                'guess_lang': False,
                            }
                        })
    
    def get_tags(self):
        return [tag.name for tag in self.tags.order_by(Tag.name.asc())]

    def set_tag(self, *args):
        tags = []
        for tag in args:
            if not tag:
                continue
            try:
                tag = Tag.get(Tag.name == tag)
            except Tag.DoesNotExist:
                tag = Tag.create(name=tag)
            tags.append(tag)
        for tag in self.tags:
            if tag.name not in tags:
                self.tags.remove(tag)
        self.tags.add(tags)

    def save(self, *args, **kwargs):
        # Generate a URL-friendly representation of the entry's title.
        if not self.slug:
            self.slug = slugify(self.title.lower())
        return super(Post, self).save(*args, **kwargs)


class Tag(BaseModel):
    name = CharField(unique=True)
    posts = ManyToManyField(Post, backref='tags', on_delete='CASCADE')


@app.before_first_request
def before_first_request():
    """Setup email alerts."""
    if not app.debug and app.config['MAIL_SERVER']:
        auth = None
        if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
            auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        mail_handler = SMTPHandler(
            mailhost=(app.config['MAIL_SERVER'], 
                    app.config['MAIL_PORT']),
            fromaddr=app.config['MAIL_FROMADDR'],
            toaddrs=app.config['MAIL_TOADDRS'], 
            subject='Microblog Failure',
            credentials=auth, 
            secure=() if app.config['MAIL_USE_TLS'] else None)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


@app.before_request
def before_request():
    g.authenticated = 'authenticated' in session


@app.route('/favicon.ico')
def favicon():
    """
    https://flask.palletsprojects.com/en/1.1.x/patterns/favicon/
    """
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.authenticated:
        flash('You are already logged in', 'warning')
        return redirect(url_for('posts'))
    if request.method == 'POST':
        if (
            (app.config['AUTH_USERNAME'] == request.form.get('username')) and 
            (app.config['AUTH_PASSWORD'] == request.form.get('password'))
        ):
            session['authenticated'] = True
            flash('You are now logged in', 'info')
            return redirect(url_for('posts'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    if g.authenticated:
        session.clear()
        flash('You were logged out', 'info')
    return redirect(url_for('posts'))


@app.route('/post', methods=['GET', 'POST'])
@app.route('/post/<slug>', methods=['GET', 'POST'])
@requires_auth
def form(slug=None):
    error = None
    if slug:
        post = get_object_or_404(Post, Post.slug == slug)
    else:
        post = Post()
    if request.method == 'POST':
        created = post.id is None
        post.title = request.form['title']
        post.slug = slugify(post.title)
        post.description = request.form['description']
        post.content = request.form['content']
        post.published = 'published' in request.form
        tags = map(lambda s: s.strip(), request.form['tags'].split(','))
        try:
            post.save()
            post.set_tag(*tags)
        except IntegrityError as exc:
            error = exc
        else:
            flash('Post %s' % ('created' if created else 'saved'), 'info')
            return redirect(url_for('form', slug=post.slug))
    return render_template('form.html', post=post, error=error)


@app.route('/post/<slug>/delete')
@requires_auth
def delete(slug):
    post = get_object_or_404(Post, Post.slug == slug)
    post.delete_instance()
    flash('Post deleted', 'info')
    return redirect(url_for('posts'))


@app.route('/posts/<slug>')
def post(slug):
    query = Post.select().where(Post.slug == slug)
    if not g.authenticated:
        query = query.where(Post.published == True)
    post = query.first()
    if post is None:
        abort(404)
    tags = post.get_tags()
    tweet_url = None
    if app.config['BLOG_AUTHOR_TWITTER']:
        params = {
            'hashtags': ','.join(tags),
            'text': post.title + ' by @' + app.config['BLOG_AUTHOR_TWITTER'],
            'url': url_for('post', slug=post.slug, _external=True),
        }
        tweet_url = 'https://twitter.com/share?%s' % (
            urllib.parse.urlencode(params, doseq=False))
    return render_template('post.html', 
                           title=post.title, 
                           description=post.description,
                           post=post,
                           tags=tags,
                           tweet_url=tweet_url)


@app.route('/drafts')
@requires_auth
def drafts():
    q = request.args.get('q')
    query = Post.select().where(Post.published == False)
    if q:
        query = query.where((Post.title.contains(q)) |
                            (Post.description.contains(q)))
    posts = query.order_by(Post.timestamp.desc())
    return render_template('posts.html', posts=posts, query=q)


@app.route('/posts')
@app.route('/')
def posts():
    q = request.args.get('q')
    tag = request.args.get('tag')
    if tag:
        try:
            query = Tag.get(Tag.name == tag).posts
        except Tag.DoesNotExist:
            query = Post.select()
    else:
        query = Post.select()
    if q:
        query = query.where((Post.title.contains(q)) |
                            (Post.description.contains(q)))
    posts = (query
             .where(Post.published == True)
             .order_by(Post.timestamp.desc()))
    return render_template('posts.html', posts=posts, query=q, tag=tag)


@cli.command('initdb')
def initdb():
    """Safely initialize the database."""
    db.create_tables(
        [Post, Tag, Tag.posts.get_through_model()], safe=True)