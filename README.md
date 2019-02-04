# utopian-bot
Contains Python scripts used to handle all things related to the @utopian-io account's voting, unvoting, resteeming etc.

# Installing

The Utopian bot was made using Python3.6. For a quick and easy way to install it is recommended you install the [Anaconda Distribution](https://www.anaconda.com/what-is-anaconda/). 

## Python packages
Once Python is installed you can install the required packages in your virtual environment like so

```bash
$ python -m venv venv
$ . venv/bin/active
$ (venv) pip install -r requirements.txt
```

If you encounter any problems while installing the Python packages you might be missing some other required packages. On Ubuntu you can solve this by installing the following packages

```
sudo apt-get install build-essential libssl-dev python-dev
```

## Sheet API
Since the bot also works with Google sheets you will need create a project in [Google's API manager](https://console.cloud.google.com/apis/dashboard) and add the Google sheet API to the project. Once created you will also need to add credentials to the project and make it so application data is accessible by selecting that option.

Next you will need to create a service account with the project editor role. Clicking continue will generate a JSON file that you should add to the project's folder and rename it `client_secret.json`. In this file there should be a key called "client_email" - you should share the spreadsheet with this email address.

# Usage

Once everything has been installed you need to set up your `beem` wallet and import the account you want to use. This can be done as follows

```bash
$ beempy createwallet --wipe
$ beempy importaccount --roles posting <account>
```

After this you should set up your crontab with `crontab -e`. It's important you use the full path of both Python and the script, which you can find with `which python` and `realpath utopian_bot/upvote_bot.py`. You should also set the `UNLOCK` environment variable inside the crontab itself so it unlocks the wallet automatically (so this should be the wallet's password you set earlier).

For the trail an IBM Watson account is used, so inside the crontab the environment variables `WATSON_USERNAME` and `WATSON_PASSWORD` must be set for the
username and password respectively.

If you want to run the bot every 5 minutes for example your crontab file will look something like this

```
UNLOCK="123456"
WATSON_USERNAME="username"
WATSON_PASSWORD="password"
*/5 * * * * /home/amos/Documents/utopian-bot/venv/bin/python /home/amos/Documents/utopian-bot/utopian_bot/upvote_bot.py
```

---

That's it! If you have any questions you can contact me on Discord at Amos#4622.
