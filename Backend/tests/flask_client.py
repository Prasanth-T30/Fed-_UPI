"""Small adapter for the existing API tests."""

import io


class Response:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.content = response.data
        self.text = response.data.decode("utf-8", errors="replace")

    def json(self):
        return self._response.get_json()


class TestClient:
    __test__ = False

    def __init__(self, app):
        self.client = app.test_client()

    def request(self, method, path, **kwargs):
        files = kwargs.pop("files", None)
        params = kwargs.pop("params", None)
        if files:
            kwargs["data"] = {key: (io.BytesIO(data), name) for key, (name, data) in files.items()}
        if params:
            kwargs["query_string"] = params
        return Response(self.client.open(path, method=method, **kwargs))

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def options(self, path, **kwargs):
        return self.request("OPTIONS", path, **kwargs)
