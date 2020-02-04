import json


def get_all(model_cls_name, page_size=25, page=1, sort=None, **kwargs):
    """
    Get a list of documents from the model_cls_name (models.<ClassName>).
    The query is provided as key-value pairs in kwargs.
    sort : sort field name (-name to sort in descending)
    page_size: number of documents to return
    page: page number
    """
    rsp = model_cls_name.objects(**kwargs)
    if sort:
        rsp = rsp.order_by(sort)
    page_size = int(page_size)
    page = int(page)
    start = (page - 1) * page_size
    end = start + page_size
    docs = json.loads(rsp[start:end].to_json())
    for doc in docs:
        doc['id'] = doc['_id']['$oid']
        doc.pop('_id', None)
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


def get(model_cls_name, **kwargs):
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
        return item


def create_item(model_cls_name, json_body):
    item = model_cls_name(**json_body)
    item.save()        


def update(model_cls_name, src_item_query, **kwargs):
    """
    src_item_query is a dict to find the source item to update
    **kwargs is key-value arguments to update. The key is the same
    as required by mongoengine
    """
    item = model_cls_name.objects(**src_item_query).modify(new=True, **kwargs)
