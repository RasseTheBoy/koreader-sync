# -*- coding: utf-8 -*-
from distutils.util import strtobool
from pydantic import BaseModel
from dotenv import load_dotenv
from tinydb import Query, TinyDB
from typing import Optional
from uuid import uuid1
from time import time
from os import getenv
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse


app = FastAPI(openapi_url=None, redoc_url=None)
db = TinyDB('data/db.json')
users = db.table('users')
documents = db.table('documents')
load_dotenv()


class KosyncUser(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None

class KosyncDocument(BaseModel):
    document: Optional[str] = None
    progress: Optional[str] = None
    percentage: Optional[float] = None
    device: Optional[str] = None
    device_id: Optional[str] = None


@app.post('/users/create')
def register(kosync_user: KosyncUser) -> JSONResponse:
    """Register a new user (if OPEN_REGISTRATIONS is set to True).
    
    :param KosyncUser kosync_user: The user to be registered.
    
    :return: JSONResponse
    """
    # Registrerations are not allowed on this server
    if not strtobool(getenv('OPEN_REGISTRATIONS', 'True')):
        return JSONResponse(status_code=403, content='This server is currently not accepting new registrations.')

    # Check if username or password is missing
    elif None in (kosync_user.username, kosync_user.password):
        return JSONResponse(status_code=400, content={'message': 'Invalid request'})
    
    # Check if user already exists
    QUser = Query()
    
    if users.contains(QUser.username == kosync_user.username):
        return JSONResponse(status_code=409, content='Username is already registered.')

    # Register new user
    elif users.insert({'username': kosync_user.username, 'password': kosync_user.password}):
        return JSONResponse(status_code=201, content={'username': kosync_user.username})
    
    # Something went wrong
    return JSONResponse(status_code=500, content='Unknown server error')


@app.get('/users/auth')
def authorize(
    x_auth_user: Optional[str] = Header(None),
    x_auth_key: Optional[str] = Header(None)
) -> JSONResponse:
    """Check if username and password combination is valid.
    
    :param str x_auth_user: The username.
    :param str x_auth_key:

    :return: JSONResponse
    """
    # Check if username or password is missing
    if not (x_auth_user and x_auth_key):
        return JSONResponse(status_code=401, content={'message': 'Unauthorized'})
    
    QUser = Query()
    
    # Check if username is in database
    if not users.contains(QUser.username == x_auth_user):
        return JSONResponse(status_code=403, content={'message': 'Forbidden'})
    
    # Check username and password combination
    elif not users.contains((QUser.username == x_auth_user) & (QUser.password == x_auth_key)):
        return JSONResponse(status_code=401, content={'message': 'Unauthorized'})
    
    # Authentication successful
    return JSONResponse(status_code=200, content={'authorized': 'OK'})


@app.put('/syncs/progress')
def update_progress(
    kosync_document: KosyncDocument,
    x_auth_user: Optional[str] = Header(None),
    x_auth_key: Optional[str] = Header(None)
) -> JSONResponse:
    """Update progress of a document.

    :param KosyncDocument kosync_document: The document to be updated.
    :param str x_auth_user: The username.
    :param str x_auth_key: The password.
    
    :return: JSONResponse
    """
    # Check if username or password is missing
    if not (x_auth_user and x_auth_key):
        return JSONResponse(status_code=401, content={'message': 'Unauthorized'})
    
    QUser = Query()
    QDocument = Query()
    
    # Check if username is in database
    if not users.contains(QUser.username == x_auth_user):
        return JSONResponse(status_code=403, content={'message': 'Forbidden'})
    
    # Check username and password combination
    elif not users.contains((QUser.username == x_auth_user) & (QUser.password == x_auth_key)):
        return JSONResponse(status_code=401, content={'message': 'Unauthorized'})
    
    # Check if document is in database
    elif None in (
        kosync_document.document,
        kosync_document.progress,
        kosync_document.percentage,
        kosync_document.device,
        kosync_document.device_id
    ):
        return JSONResponse(status_code=500, content='Unknown server error')
    
    # Update document in database
    timestamp = int(time())
    if documents.upsert(
        {
            'username': x_auth_user,
            'document': kosync_document.document,
            'progress': kosync_document.progress,
            'percentage': kosync_document.percentage,
            'device': kosync_document.device,
            'device_id': kosync_document.device_id,
            'timestamp': timestamp
        },
        (QDocument.username == x_auth_user) & (QDocument.document == kosync_document.document)
    ):
        return JSONResponse(
            status_code=200,
            content={'document': kosync_document.document, 'timestamp': timestamp}
        )
        
    # Something went wrong
    return JSONResponse(status_code=500, content='Unknown server error')


@app.get('/syncs/progress/{document}')
def get_progress(
    document: Optional[str] = None,
    x_auth_user: Optional[str] = Header(None),
    x_auth_key: Optional[str] = Header(None)
) -> JSONResponse:
    """Get the progress of a document.
    
    :param str document: The document to get the progress of.
    :param str x_auth_user: The username.
    :param str x_auth_key: The password.
    
    :return: JSONResponse
    """
    # Check if username or password is missing
    if not (x_auth_user and x_auth_key):
        return JSONResponse(status_code=401, content={'message': 'Unauthorized'})
    
    # Check if document parameter exists
    elif document is None:
        return JSONResponse(status_code=500, content='Unknown server error')

    QUser = Query()
    QDocument = Query()

    # Check if username is in database
    if not users.contains(QUser.username == x_auth_user):
        return JSONResponse(status_code=403, content={'message': 'Forbidden'})

    # Check username and password combination
    elif not users.contains((QUser.username == x_auth_user) & (QUser.password == x_auth_key)):
        return JSONResponse(status_code=401, content={'message': 'Unauthorized'})
    
    # Get document progress if user has the document
    result = documents.search((QDocument.username == x_auth_user) & (QDocument.document == document))
    
    # Document not found
    if not result:
        return JSONResponse(status_code=404, content={'message': 'Not found'})
    
    # Select the first result
    result = result[0]
    
    # Get device ID from either database or generate one; depends on the 'RECEIVE_RANDOM_DEVICE_ID' environment variable
    device_id = str(uuid1().hex).upper() if strtobool(getenv('RECEIVE_RANDOM_DEVICE_ID', 'False')) else result['device_id']
     
    # Return document progress
    return JSONResponse(
        status_code=200,
        content={
            'username': x_auth_user,
            'document': result['document'],
            'progress': result['progress'],
            'percentage': result['percentage'],
            'device': result['device'],
            'device_id': device_id,
            'timestamp': result['timestamp']
        }
    )
    
    
@app.get('/healthstatus')
def get_healthstatus() -> JSONResponse:
    """Get the health status of the server.

    :return: JSONResponse
    """
    return JSONResponse(status_code=200, content={'message': 'healthy'})
