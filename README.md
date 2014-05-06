# Alpha

This is an open-source version of alpha.app.net, the web microblogging client for App.net.

## Getting Started

There are a couple of prerequisites for getting Alpha up and running.

* **An App.net Developer account**
* **Python** - Alpha is a Django app, so you'll need a Python 2.7 environment. We suggest running it inside a virtualenv.
* **Node.js, npm** - You will need Node.js and npm installed to build the static files. If you don't already have Node.js and npm installed, you can follow this [installation guide](http://www.joyent.com/blog/installing-node-and-npm).
* **Sass** - We are also using [Sass](http://sass-lang.com/) to compile CSS. To install Sass, follow the [Install Sass Guide](http://sass-lang.com/install).

### Create an App.net App

Create an App.net application by visiting https://account.app.net/developer/apps/ and choosing "Create An App." Be sure to note your Client ID and Client Secret -- you'll need them in a second.

### Set up your environment

Alpha must be configured with your Client ID and Client Secret as well as an App Access Token for unauthenticated views. Care must be taken to ensure that you do not check in your secrets, so we recommend exporting them as environment variables.

Start by exporting your Client ID and Client Secret:

```sh
export SOCIAL_AUTH_APPDOTNET_KEY=client_id
export SOCIAL_AUTH_APPDOTNET_SECRET=client_secret
```

Now generate an App Access Token:

```sh
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "grant_type=client_credentials" \
    -d "client_id=$SOCIAL_AUTH_APPDOTNET_KEY" -d "client_secret=$SOCIAL_AUTH_APPDOTNET_SECRET" \
    "https://account.app.net/oauth/access_token"
```

You'll see something like the following:

```js
{"access_token":"YOUR_NEW_APP_ACCESS_TOKEN","token":{"scopes":[],"app":{"link":"http://alpha.app.net","name":"Pau","client_id":"YOUR_CLIENT_ID"},"client_id":"YOUR_CLIENT_ID","is_app_token":true}}
```

Copy out the access token part and export that into your environment as well.

```sh
export APP_TOKEN=YOUR_NEW_APP_ACCESS_TOKEN
```

Finally, you'll need to make sure that Django is using a unique, secret value for SECRET_KEY. In this skeleton project, we've made it so that SECRET_KEY comes from an environment variable.

Generate a key with, e.g., `pwgen -N 1 -s 64`, and set it as an environment variable:

```sh
pwgen -N 1 -s 64
long-random-key-hello
export SECRET_KEY=long-random-key-hello
```

When running the application, you'll need to export these variables every time (or export them in a shell script which wraps them!)

Next, create a virtualenv into which we can install our Python requirements and get a dev server up and running:

```sh
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
# Create the database
python manage.py syncdb
# Answer no when it asks you if you would like to create a superuser
```

That should be it!

## Running Alpha in development mode

To run the dev server, do the following:

```sh
python manage.py runserver
```

You should now be able to visit http://127.0.0.1:8000 and see the main splash screen for the Alpha project. If everything is setup you should be able to login and start using your own version of Alpha.

## Start the static asset compiler

Alpha uses a Node.js-based static build tool called gulp to compile static assets and recompile them on changes. If you want to make changes to the static assets (CSS, Javascript, etc.), you'll need to run the following:

```sh
cd pau
npm install
./node_modules/.bin/gulp
```

gulp will start watching your files for changes. When you save any static asset file, gulp will recompile the static assets.

You can run devserver simultaneously in another shell and you should be able to make changes to your static assets and see your changes reflected when you refresh the page.

## Deploying Alpha

There are a number of ways to deploy Alpha. Since this is a pretty normal Django app you can find instructions [here](https://docs.djangoproject.com/en/1.6/howto/deployment/)

You can even deploy to heroku, here's how. Make sure you have the heroku-toolbelt installed.

```sh
heroku create
heroku config:set SOCIAL_AUTH_APPDOTNET_KEY="$SOCIAL_AUTH_APPDOTNET_KEY" SOCIAL_AUTH_APPDOTNET_SECRET="$SOCIAL_AUTH_APPDOTNET_SECRET" APP_TOKEN="$APP_TOKEN" SECRET_KEY="$SECRET_KEY"
git push heroku master
heroku run python manage.py syncdb
```

You should now be able to visit your new heroku instance and use Alpha.
