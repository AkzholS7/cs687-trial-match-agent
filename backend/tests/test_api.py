"""API tests: each test gets a fresh SQLite database file."""
import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / 'test.db'))
    app.config['TESTING'] = True
    return app.test_client()


def example(client, i=0):
    return client.get('/api/examples').get_json()[i]['summary']


def test_health_and_collections(client):
    assert client.get('/api/health').get_json()['status'] == 'ok'
    assert client.get('/api/collections').get_json() == [{'name': 'demo', 'trials': 15}]


def test_trial_search_and_detail(client):
    page = client.get('/api/trials?collection=demo&q=diabetes&limit=5').get_json()
    assert 0 < page['total'] and len(page['items']) <= 5
    tid = page['items'][0]['id']
    assert client.get(f'/api/trials/demo/{tid}').get_json()['id'] == tid
    assert client.get('/api/trials/demo/NOPE').status_code == 404
    assert client.get('/api/trials?limit=x').status_code == 400


def test_match_saves_a_run(client):
    res = client.post('/api/match', json={'summary': example(client), 'settings': {'top_k': 5, 'alpha': 0.4}})
    assert res.status_code == 200
    body = res.get_json()
    assert body['run_id'] and len(body['trials']) <= 5 and body['settings']['alpha'] == 0.4
    runs = client.get('/api/runs').get_json()
    assert runs[0]['id'] == body['run_id']
    assert client.get(f"/api/runs/{body['run_id']}").get_json()['result']['counts'] == body['counts']


def test_match_without_saving(client):
    body = client.post('/api/match', json={'summary': example(client), 'save': False}).get_json()
    assert 'run_id' not in body and client.get('/api/runs').get_json() == []


@pytest.mark.parametrize('payload,code', [
    ({}, 400),
    ({'summary': '   '}, 400),
    ({'summary': 'x' * 6000}, 400),
    ({'summary': 'A 50-year-old man.', 'collection': 'missing'}, 404),
    ({'summary': 'A 50-year-old man.', 'settings': {'alpha': 2}}, 400),
    ({'summary': 'A 50-year-old man.', 'settings': {'top_k': 'many'}}, 400),
    ({'summary': 'A 50-year-old man.', 'answers': [1]}, 400),
    ({'summary': 'A 50-year-old man.', 'answers': {'age': 'old'}}, 400),
])
def test_match_validation(client, payload, code):
    assert client.post('/api/match', json=payload).status_code == code


def test_decisions_and_stats(client):
    body = client.post('/api/match', json={'summary': example(client)}).get_json()
    run_id, tid = body['run_id'], body['trials'][0]['id']
    url = f'/api/runs/{run_id}/decisions/{tid}'
    assert client.put(url, json={'decision': 'accept', 'note': 'good fit'}).get_json()[tid]['decision'] == 'accept'
    assert client.put(url, json={'decision': 'reject'}).get_json()[tid]['decision'] == 'reject'   # update, not duplicate
    assert client.put(url, json={'decision': 'maybe'}).status_code == 400
    assert client.put(f'/api/runs/{run_id}/decisions/NOT-IN-RUN', json={'decision': 'accept'}).status_code == 404
    stats = client.get('/api/stats').get_json()
    assert stats['runs'] == 1 and stats['rejected'] == 1 and stats['accepted'] == 0
    assert client.delete(url).get_json() == {}


def test_delete_run_cascades(client):
    body = client.post('/api/match', json={'summary': example(client)}).get_json()
    client.put(f"/api/runs/{body['run_id']}/decisions/{body['trials'][0]['id']}", json={'decision': 'accept'})
    assert client.delete(f"/api/runs/{body['run_id']}").status_code == 204
    assert client.get(f"/api/runs/{body['run_id']}").status_code == 404
    assert client.get('/api/stats').get_json()['accepted'] == 0


def test_benchmark_results(client):
    data = client.get('/api/benchmark').get_json()
    assert data['sigir_full']['0.4']['ndcg'] == 0.1491
