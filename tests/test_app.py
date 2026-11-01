import json


def call_ok(response, expected=200):
    assert response.status_code == expected, response.text
    return response.json()


def make_store(client, name='Walmart One'):
    return call_ok(client.post('/api/stores', json={'name': name, 'location': 'Test Town', 'store_code': '1234'}), 201)['id']


def make_aisle(client, store, code, description=''):
    return call_ok(client.post(f'/api/stores/{store}/aisles', json={'code': code, 'description': description}), 201)['id']


def test_fresh_list_and_basic_flow(client):
    assert call_ok(client.get('/health'))['status'] == 'ok'
    s = call_ok(client.get('/api/state'))
    assert s['items'] == [] and len(s['categories']) >= 5
    a = call_ok(client.post('/api/items', json={'name':'Milk'}),201)['id']
    b = call_ok(client.post('/api/items', json={'name':'Bread'}),201)['id']
    assert call_ok(client.get('/api/state'))['items'][0]['quantity'] == 1
    call_ok(client.patch(f'/api/items/{a}', json={'quantity': 3, 'checked':True}))
    state = call_ok(client.get('/api/state'))
    assert [i['checked'] for i in state['items']] == [1,0]
    assert state['items'][0]['quantity'] == 3
    assert call_ok(client.post('/api/items/clear-completed'))['removed'] == 1
    assert [i['name'] for i in call_ok(client.get('/api/state'))['items']] == ['Bread']
    response = client.post('/api/items',json={'name':'bread'})
    assert response.status_code == 409 and response.json()['existing_id'] == b
    call_ok(client.delete(f'/api/items/{b}'))
    assert not call_ok(client.get('/api/state'))['items']


def test_store_specific_sort_and_shared_list(client):
    first, second = make_store(client, 'Walmart'), make_store(client, 'Ace Hardware')
    a7 = make_aisle(client,first,'A7','Pasta')
    dairy = make_aisle(client,first,'Dairy','Cold foods')
    cold = make_aisle(client,second,'C9','Cold')
    cat = next(c['id'] for c in call_ok(client.get('/api/state'))['categories'] if c['name']=='Dry Pasta')
    call_ok(client.put(f'/api/stores/{first}/categories/{cat}',json={'aisle_id': a7}))
    call_ok(client.put(f'/api/stores/{second}/categories/{cat}',json={'aisle_id': cold}))
    pasta = call_ok(client.post('/api/items',json={'name':'Spaghetti'}),201)['id']
    milk = call_ok(client.post('/api/items',json={'name':'Milk'}),201)['id']
    call_ok(client.put(f'/api/stores/{first}/products',json={'product_name':'Milk','aisle_id':dairy}))
    walmart = call_ok(client.get(f'/api/state?store_id={first}'))
    ace = call_ok(client.get(f'/api/state?store_id={second}'))
    assert [x['name'] for x in walmart['items']] == ['Spaghetti', 'Milk']
    assert ace['items'][0]['name'] == 'Spaghetti'
    assert ace['items'][0]['aisle_code'] == 'C9'
    assert ace['items'][1]['aisle_code'] is None
    assert len(call_ok(client.get('/api/state'))['items']) == 2
    call_ok(client.put(f'/api/stores/{first}/aisles/order',json={'ids':[dairy,a7]}))
    assert [x['name'] for x in call_ok(client.get(f'/api/state?store_id={first}'))['items']] == ['Milk','Spaghetti']
    call_ok(client.patch(f'/api/items/{milk}', json={'checked':True}))
    assert next(x for x in call_ok(client.get(f'/api/state?store_id={second}'))['items'] if x['id']==milk)['checked'] == 1


def test_category_memory_and_overrides(client):
    store = make_store(client)
    a1, a2 = make_aisle(client,store,'A1'),make_aisle(client,store,'A2')
    categories = call_ok(client.get('/api/state'))['categories']
    cat = next(c['id'] for c in categories if c['name']=='Dry Pasta')
    call_ok(client.put(f'/api/stores/{store}/categories/{cat}',json={'aisle_id':a1}))
    item = call_ok(client.post('/api/items',json={'name':'Penne Pasta'}),201)['id']
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['aisle_code'] == 'A1'
    call_ok(client.put(f'/api/stores/{store}/products',json={'product_name':'Penne Pasta','aisle_id':a2}))
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['aisle_code'] == 'A2'
    call_ok(client.put(f'/api/stores/{store}/categories/{cat}',json={'aisle_id':a2}))
    call_ok(client.put(f'/api/stores/{store}/products',json={'product_name':'Penne Pasta','aisle_id':None}))
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['location_source'] == 'category'
    call_ok(client.patch(f'/api/items/{item}',json={'category_id':None}))
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['aisle_code'] is None


def test_export_preview_merge_replace_roundtrip(client):
    a, b = make_store(client,'Original'),make_store(client,'Target')
    z, f = make_aisle(client,a,'Z9','Dry'),make_aisle(client,a,'F2','Frozen')
    cat = next(c['id'] for c in call_ok(client.get('/api/state'))['categories'] if c['name']=='Dry Pasta')
    call_ok(client.put(f'/api/stores/{a}/categories/{cat}',json={'aisle_id':z}))
    call_ok(client.put(f'/api/stores/{a}/products',json={'product_name':'SpaghettiOs','aisle_id':z}))
    call_ok(client.post('/api/items',json={'name':'SpaghettiOs'}),201)
    payload = call_ok(client.get(f'/api/stores/{a}/export'))
    assert payload['format']=='yagl-store-layout' and payload['schema_version']==1
    assert [a['code'] for a in payload['aisles']] == ['Z9','F2']
    preview = call_ok(client.post(f'/api/stores/{b}/import/preview',json={'payload':payload}))
    assert preview['aisles']==2
    call_ok(client.post(f'/api/stores/{b}/import',json={'mode':'merge','payload':payload}))
    output = call_ok(client.get(f'/api/stores/{b}/export'))
    for name in ['aisles','category_locations','product_locations']:
        assert output[name]==payload[name]
    assert call_ok(client.get('/api/state'))['items'][0]['name']=='SpaghettiOs'
    make_aisle(client,b,'X1')
    call_ok(client.post(f'/api/stores/{b}/import',json={'mode':'replace','payload':payload}))
    assert [x['code'] for x in call_ok(client.get(f'/api/state?store_id={b}'))['layout']['aisles']] == ['Z9','F2']
    assert len(call_ok(client.get(f'/api/state?store_id={a}'))['layout']['aisles']) == 2


def test_invalid_import_rolls_back(client):
    store=make_store(client)
    keep=make_aisle(client,store,'Keep')
    payload=call_ok(client.get(f'/api/stores/{store}/export'))
    payload['product_locations']=[{'product':'Milk','aisle':'FAKE'}]
    response=client.post(f'/api/stores/{store}/import',json={'mode':'replace','payload':payload})
    assert response.status_code==400
    assert call_ok(client.get(f'/api/state?store_id={store}'))['layout']['aisles'][0]['id']==keep


def test_websocket_change_notification(client):
    with client.websocket_connect('/api/live') as socket:
        assert socket.receive_json()['type']=='ready'
        call_ok(client.post('/api/items',json={'name':'Coffee'}),201)
        assert socket.receive_json()['type']=='changed'


def test_input_validation(client):
    assert client.post('/api/items',json={'name':'  '}).status_code==400
    assert client.post('/api/items',json={'name':'Milk','quantity':0}).status_code==400
    assert client.post('/api/items',json={'name':'Milk','quantity':True}).status_code==400
    assert client.put('/api/stores/999/categories/5',json={'aisle_id':12}).status_code==404
    store=make_store(client)
    aisle=make_aisle(client,store,'A7')
    assert client.put(f'/api/stores/{store}/aisles/order',json={'ids':[]}).status_code==400
    assert client.put(f'/api/stores/{store}/categories/1',json={'aisle_id':999}).status_code==400
    assert client.patch('/api/items/999',json={'checked':True}).status_code==404


def test_learning_persists_after_done_and_new_item(client):
    store=make_store(client)
    zone=make_aisle(client,store,'A12')
    canned=next(c['id'] for c in call_ok(client.get('/api/state'))['categories'] if c['name']=='Canned Foods')
    original=call_ok(client.post('/api/items',json={'name':'SpaghettiOs'}),201)['id']
    call_ok(client.patch(f'/api/items/{original}',json={'category_id':canned,'checked':True}))
    call_ok(client.put(f'/api/stores/{store}/categories/{canned}',json={'aisle_id':zone}))
    assert call_ok(client.post('/api/items/clear-completed'))['removed']==1
    call_ok(client.post('/api/items',json={'name':'SpaghettiOs'}),201)
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['aisle_code']=='A12'


def test_merge_preserves_custom_route_and_location(client):
    a, b=make_store(client,'Shared'),make_store(client,'Personal')
    original=make_aisle(client,a,'A7')
    cat=next(c['id'] for c in call_ok(client.get('/api/state'))['categories'] if c['name']=='Dry Pasta')
    call_ok(client.put(f'/api/stores/{a}/categories/{cat}',json={'aisle_id':original}))
    own=make_aisle(client,b,'MySpecialZone')
    call_ok(client.put(f'/api/stores/{b}/categories/{cat}',json={'aisle_id':own}))
    payload=call_ok(client.get(f'/api/stores/{a}/export'))
    call_ok(client.post(f'/api/stores/{b}/import',json={'mode':'merge','payload':payload}))
    s=call_ok(client.get(f'/api/state?store_id={b}'))['layout']
    assert [a['code'] for a in s['aisles']]==['MySpecialZone','A7']
    assert next(m['aisle_id'] for m in s['category_locations'] if m['category_id']==cat)==own


def test_html_and_assets_serve(client):
    page=client.get('/')
    assert page.status_code==200 and 'Yet Another Grocery List' in page.text
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/assets/style.css').status_code==200


def test_existing_unmapped_item_learns_new_category_rules(client):
    store=make_store(client)
    zone=make_aisle(client,store,'H5')
    item=call_ok(client.post('/api/items',json={'name':'Special Widgets'}),201)['id']
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['category_id'] is None
    category=call_ok(client.post('/api/categories',json={'name':'Widgets','keywords':'special widgets'}),201)['id']
    call_ok(client.put(f'/api/stores/{store}/categories/{category}',json={'aisle_id':zone}))
    state=call_ok(client.get(f'/api/state?store_id={store}'))
    assert state['items'][0]['id']==item
    assert state['items'][0]['aisle_code']=='H5'
    assert state['items'][0]['category_name']=='Widgets'
    call_ok(client.patch(f'/api/items/{item}',json={'checked':True}))
    call_ok(client.post('/api/items/clear-completed'))
    call_ok(client.post('/api/items',json={'name':'Special Widgets'}),201)
    assert call_ok(client.get(f'/api/state?store_id={store}'))['items'][0]['aisle_code']=='H5'
