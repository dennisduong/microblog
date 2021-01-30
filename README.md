# microblog

A microblog web app written in Python

# About

The main goal of this project is to create a microblog that I can easily manage. I personally use a SQLite database to store my blog posts and tags. Blog posts are written with markdown as the primary writing language.

# Features

* Markdown support using the Python-Markdown library
    * Code syntax highlighting done with pygments under the hood
    * Supports admonitions
* Support for SQLite, PostgreSQL and MySQL databases via peewee
* Tag system
* Simple search system
* Tweet share button for blog posts
* Email notifications when an exception occurs
* Google analytics integration

# Configuration

Configuration can be done using environment variables, a JSON file (`/etc/microblog.json`) or a python file (`/etc/microblog.conf`).

| Name                | Description                 | Default                                         |
--------------------- | ----------------------------| -------------------------------------------------
`SECRET_KEY`          | Set this with a UUID        | `shh...`                                        |
`DATABASE_URL`        | The database connection url | `sqlite:///microblog.db`                        |
`AUTH_USERNAME`       | Admin username              | `admin`                                         |
`AUTH_PASSWORD`       | Admin username              | `password`                                      |
`BLOG_BRAND`          | The navbar brand text       | `microblog`                                     |
`BLOG_TITLE`          | The home page title         | `Microblog`                                     |
`BLOG_DESCRIPTION`    | The home page description   | `A microblog from a developer who does things.` |
`BLOG_AUTHOR_NAME`    | Author's name               | `Microblog Inc.`                                |
`BLOG_AUTHOR_GITHUB`  | Author's GitHub username    |                                                 |
`BLOG_AUTHOR_TWITTER` | Author's GitHub username    |                                                 |
`PROXYFIX_X_FOR`      |                             | `0`                                             |
`PROXYFIX_X_PROTO`    |                             | `0`                                             |
`PROXYFIX_X_HOST`     |                             | `0`                                             |
`MAIL_SERVER`         |                             |                                                 |
`MAIL_PORT`           |                             |                                                 |
`MAIL_USERNAME`       |                             |                                                 |
`MAIL_PASSWORD`       |                             |                                                 |
`MAIL_USE_TLS`        |                             |                                                 |
`MAIL_FROMADDR`       |                             |                                                 |
`MAIL_TOADDRS`        |                             |                                                 |

For `PROXYFIX_X_*` config, see [X-Forwarded-For Proxy Fix](https://werkzeug.palletsprojects.com/en/1.0.x/middleware/proxy_fix/)