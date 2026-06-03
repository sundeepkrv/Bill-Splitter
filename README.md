# Bill Splitter

A simple and intuitive bill splitter application on the similar lines of split wise. This application can be used to create anonymous groups for sharing amongst friends and colleagues. No sign-up / no email requirement / no backtracking. This application can be self hosted or you can use my weblink for creation of groups and sharing.

## Development

This app has been developed in flask using python.

## Deployment

### For Unix/MacOS

Clone the project

```bash
  git clone https://github.com/sundepkrv/Bill-Splitter.git
```

Go to the project directory

```bash
  cd Bill-Splitter
```

Create a virtual environment and install requirements

```bash
  python3 -m venv venv
  source ./venv/bin/activate
  pip install -r requirements.txt
```

Start the server for local deployment

```bash
  python3 app.py
```

Using gunicorn for production deployment

```bash
  gunicorn --workers:2 app:app
```

### For Windows

Clone the project

```bash
  git clone https://github.com/sundepkrv/Bill-Splitter.git
```

Go to the project directory

```bash
  cd Bill-Splitter
```

Create a virtual environment and install requirements

```bash
  python -m venv venv
  .\venv\Scripts\activate
  pip install -r requirements.txt
```

Start the server for local deployment

```bash
  python app.py
```

Using gunicorn for production deployment

```bash
  gunicorn --workers:2 app:app
```

### Running behind a proxy network
If you are trying to install the dependencies behind a proxy network, run the following - 

```bash
  pip --proxy=http://xxx.xxx.xxx.xxx:yyyy install -r requirements.txt
```
## Tech Stack

**Client:** HTML, Tailwind, Javascript

**Server:** Flask, SQLite3

## Errors

The app may run into errors and you can debug the same using references from error traceback calls.

## Feedback and contact

[@sundeepkrv](https://github.com/sundeepkrv)
