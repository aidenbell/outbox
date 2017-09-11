# outbox - A secret email address inbox published
A quick and dirty weekend hack ... a python program to render an email inbox as a static website via IMAP. Create a secret email address and email things to it.
Outbox then can render the inbox and publish it to the world using pretty layouts
depending on the content you emailed. Everything from sharing a link to a long-form article.


## Features

- IMAP connectivity to render "unread" inbox items
- Limit publishing to certain senders (usually your personal email addres) 
- Renders pretty content depending on post email content
- Hashtags
- RSS generation
- Themeable
- GitHub Pages friendly
- Produces plain HTML, CSS and Javascript (minimal) by default

## Running Example
I run a site at (???) with the default template. I basically develop outbox and the default theme
for this site. It _should_ express the current featureset the latest release from GitHub ... take a peek!

## Installation & Usage
    ]$ git clone http://github.com/aidenbell/outbox.git
    ]$ cd src
    
You probably want to make and activate a virtualenv using the `requirements.txt` in `src`. I could do with making a `pip`
definition (PRs welcome!)

    ]$ python outbox.py --imap-username=foo@example.com --imap-password="MySecretPassw0rd!"
    reading inbox via IMAP
        > connected
        > 28 unread emails to be rendered
        > downloading
    exporting emails to ./published
    copying required assets
    done! ./published contains your site

You can then upload the contents of `src/published` to the host of your choice. It contains an `index.html` and the
rest should "just work". It works well with GitHub Pages.
    
## Hacking

Hacking the outbox source is pretty easy. The UI elements are contained in `src/templates` and are Mako templates. `src/static`
contains assets such as CSS and Javascript to be published with the site under
`{publishdir}/static/` which you can reference in templates.

### Booting the dev server
You can alter the source and test out changes, but you need to boot the built-in webserver.
The webserver will load a cached IMAP download and re-render the emails when it detects changes in the templates
or static assets in `src/themes` or the default theme. If it can't find a cache it will do the IMAP download then re-use the cache
for that session and any further sessions.

    ]$ python outbox.py ... --server=127.0.0.0.1:8080
    serving outbox on http://127.0.0.1:8080/
    watching templates,static and themes for changes
    press ctrl+c to exit
    
To delete the cache if you want to re-download some emails, use `rm src/imap_cache.pickle` and kill
the server with `ctrl+c` and run it again. 
The cache is a Pickled IMAP download, it isn't trustworthy obviously. Do not download or use other people's Pickle files,
it is for development ease only.
    
### Default theme
The default theme in `src/themes/default/templates` and `src/themes/default/static` is the de-facto references for what variables the Python
script exposes to templates through Mako. You can clone these two directories in to `src/themes/your-theme`
and start editing them. If a variable is exposed but not used in the default template then it is at-least
documented at the top of the template. To re-skin Outbox you shouldn't have to touch the Python unless
you are implementing a new feature.
    
The default theme uses the excellent Semantic UI CSS and Javascript distribution. This is pretty bulky, it isn't
a custom built distribution but as a default template it is alright for now.

## Themes
Themes are stored in `src/themes` which is empty by default. If you specify a theme with the `--theme=name`
argument then instead of the default theme Outbox will use `src/themes/name/templates` for the templates and
`src/themes/name/static` for the CSS, JS and other assets.