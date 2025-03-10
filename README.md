# hedweb

This project contains the web interface code for deploying HED tools as a web application running in a docker module. 
The instructions assume that you have cloned the `hed-python` github repository:

```
git clone https://github.com/hed-standard/hed-python
```


### Running locally
The application can be run locally on an internal test web server by calling 
the `runserver` application directly.
To do this you will have to do the following:

1. Set up a `config.py` in the same directory as `config_template.py`. 
   1.  Copy `config_template.py` to `config.py`
   2.  Change `BASE_DIRECTORY` in the `Config` class to point to the directory that
       you want the application to use to temporarily store uploads and to cache the
       HED schema.
2. Use `pip` to install `hedtool` from the 
[GitHub](https://github.com/hed-standard/hed-python) repository,
since `hedtools` is not yet available on PyPI:

   ```
       pip install git+https://github.com/hed-standard/hed-python/@master
   ```

Once this installation is complete, you can execute `runserver`. This call should
bring up a Flask test server. Paste the indicated link into a web browser, and you are 
ready to go.

### Deployment on an external webserver

#### Overview
The `deploy_hed` directory contains scripts and configuration files that are needed 
to deploy the application as a docker container. These instructions assume that you
have a Linux server with apache2 and docker installed.  

The current setup assumes that an apache web server runs inside a docker container
using internal port 80.
The docker container listens to requests on port 33000 from the local host IP
(assumed to be 127.0.0.1) of the Linux server running the docker container.
Docker forwards these requests and subsequent responses to and from its
internal server running on port 80.

If you are on the Linux server, you can run the online tools directly in a web 
browser using the address http://127.0.0.1:33000/hed.
In a production environment,
the tools are meant to be run through an Apache web server with proxies.
The description of how to set this up is described elsewhere.

#### Deploying the docker module

The instructions assume that you are in your home directory on the Linux server.
The deployment will use your home directory as a temporary staging area.
The instructions assume that you have DOCKER installed.

1. Make a deployment directory, say `deploy_hed`.
2. Download the
[hed-web deployment script](https://raw.githubusercontent.com/hed-standard/hed-web/master/deploy_hed/deploy.sh)
to your `deploy_hed` directory.
3. Change to the `deploy_hed` directory and execute of `deploy.sh` script:

```  
   cd ~/deploy_hed
```
3.  Execute the `deploy.sh` script:

```  
   sudo bash deploy.sh
```

The `deploy.sh` script will download the latest versions of the `hed-python`
and the `hed-web` repositories and deploy.