from packer.workers.celery_app import make_celery


def test_pack_routes_to_gpu_others_to_default():
    app = make_celery()
    routes = app.conf.task_routes
    assert routes["pack.run"]["queue"] == "gpu"
    assert routes["detect.run"]["queue"] == "default"
    assert routes["scan.run"]["queue"] == "default"
    assert app.conf.task_default_queue == "default"
