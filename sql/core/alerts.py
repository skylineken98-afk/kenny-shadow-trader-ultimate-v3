"""Durable notification requests; delivery requires separately configured gateway."""
import uuid
from core.db import insert,now

def enqueue(kind,payload):
    return insert('notifications',{'id':str(uuid.uuid4()),'created_at':now(),'kind':kind,'payload':payload,'status':'PENDING'})
