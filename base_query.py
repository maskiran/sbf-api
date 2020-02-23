import datetime
import json


def make_search_string(exclude_keys=None, **kwargs):
    if exclude_keys is None:
        exclude_keys = []
    valid_keys = set(kwargs.keys()) - set(exclude_keys)
    values = [str(kwargs[val]) for val in valid_keys]
    return " ".join(values)

def get_all_items(model_cls_name, page_size=25, page=1, sort=None, **kwargs):
    """
    Get a list of documents from the model_cls_name (models.<ClassName>).
    The query is provided as key-value pairs in kwargs.
    sort : sort field name (-name to sort in descending)
    page_size: number of documents to return
    page: page number
    """
    if 'search' in kwargs:
        search = kwargs.pop('search')
        rsp = model_cls_name.objects(**kwargs).search_text(search)
    else:
        rsp = model_cls_name.objects(**kwargs)
    if sort:
        rsp = rsp.order_by(sort)
    page_size = int(page_size)
    page = int(page)
    start = (page - 1) * page_size
    end = start + page_size
    if end > 0:
        docs = json.loads(rsp[start:end].to_json())
    else:
        docs = json.loads(rsp.to_json())
    for doc in docs:
        doc['id'] = doc['_id']['$oid']
        doc.pop('_id', None)
        doc['date_added'] = doc['date_added']['$date']
        doc['date_modified'] = doc['date_modified']['$date']
    next_page = page + 1
    if (next_page - 1) * page_size >= rsp.count():
        next_page = -1
    prev_page = page - 1
    if prev_page < 0:
        prev_page = -1
    body = {
        'count': rsp.count(),
        'page': page,
        'page_size': page_size,
        'next_page': next_page,
        'prev_page': prev_page,
        'start_idx': start,
        'end_idx': end,
        'items': docs,
    }
    return body


def get_item(model_cls_name, **kwargs):
    """
    Get one (first document) matching kwargs. Typically this is called
    primary/unique key like id in kwargs that should result on only one
    document. However this is flexible to return just the first document
    """
    item = model_cls_name.objects(**kwargs).first()
    if item:
        item = json.loads(item.to_json())
        item['id'] = item['_id']['$oid']
        item.pop('_id', None)
        item['date_added'] = item['date_added']['$date']
        item['date_modified'] = item['date_modified']['$date']
        return item


def create_item(model_cls_name, exclude_search=None, **kwargs):
    item = model_cls_name(**kwargs)
    # add all the values to search field
    item.search = make_search_string(exclude_search, **kwargs)
    item.date_added = datetime.datetime.utcnow()
    item.date_modified = datetime.datetime.utcnow()
    item.save()        


def update_item(model_cls_name, src_item_query, exclude_search=None, upsert=False, **kwargs):
    """
    src_item_query is a dict to find the source item to update
    **kwargs is key-value arguments to update. The key is the same
    as required by mongoengine
    """
    # ignore the base class attributes in the kwargs
    implicit_keys = ['date_added', 'date_modified', 'search', 'id', '_id']
    for key in implicit_keys:
        kwargs.pop(key, None)
    kwargs['date_modified'] = datetime.datetime.utcnow()
    item = model_cls_name.objects(**src_item_query).modify(new=True, upsert=upsert, **kwargs)
    # add search with the modified items
    json_item = json.loads(item.to_json())
    for key in implicit_keys:
        json_item.pop(key, None)
    item.search = make_search_string(exclude_search, **json_item)
    item.save()


def delete_item(model_cls_name, **kwargs):
    model_cls_name.objects(**kwargs).delete()


def distinct_items(model_cls_name):
    return model_cls_name.objects.distinct('version')   
