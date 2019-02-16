
Github Labels
=====
##### A simple script to upgrade all repository's labels of an organization


Setting up development Environment on Linux
----------------------------------

### Installing Dependencies

    $ sudo apt-get install libass-dev libpq-dev build-essential

### Setup Python environment

    $ sudo apt-get install python3-pip python3-dev
    $ sudo pip3 install virtualenvwrapper
    $ echo "export VIRTUALENVWRAPPER_PYTHON=`which python3.6`" >> ~/.bashrc
    $ echo "alias v.activate=\"source $(which virtualenvwrapper.sh)\"" >> ~/.bashrc
    $ source ~/.bashrc
    $ v.activate
    $ mkvirtualenv --python=$(which python3.6) --no-site-packages github-labels

#### Activating virtual environment
    
    $ workon github-labels

#### Upgrade pip, setuptools and wheel to the latest version and install requests

    $ pip install -U pip setuptools wheel requests


Starting On Linux
----------------------------------

## Step 1 - OAuth Token
Create an personal access token for your account with full permissions selected.

Tip: using following link to learn how:
[Create personal access token](https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/)

## Step 2 -  Run

    $ cd path/to/script
    $ GITHUB_OAUTH_TOKEN=<your_oath_token>
    $ export GITHUB_OAUTH_TOKEN
    $ ./github-labels.py <organization-title>

####  You can simply  run like this too
    $ cd path/to/script
    $ ./igithub-sync-labels.py <organization-title> --token <your_oath_token>

#### For more information about full feature list 
    $ ./github-sync-labels.py --help
