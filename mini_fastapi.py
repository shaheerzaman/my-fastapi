import inspect
from functools import wraps


class Depends:
    def __init__(self, dependency):
        self.dependency = dependency


class Fastapi:
    def __init__(self):
        self.routes = {}

    def get(self, path: str):
        """Decorator to register a path operation function."""

        def decorator(func):
            self.routes[path] = func

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def _solve_dependencies(
        self, func, request_cache: dict, context_managers: list
    ) -> dict:
        """
        The core of the DI system. This function recursively resolves dependencies.
        """
        sig = inspect.signature(func)
        kwargs_to_pass = {}

        for name, param in sig.parameters.items():
            if isinstance(param.default, Depends):
                dep_func = param.default.dependency

                # caching if we already sovled this
                if dep_func in request_cache:
                    kwargs_to_pass[name] = request_cache[dep_func]
                    continue

                # recursion: the dependency might have its own dependencies
                sub_dependencies = self._solve_dependencies(
                    dep_func, request_cache, context_managers
                )

                # handle 'yield' case
                if inspect.isgenerator(dep_func):
                    gen = dep_func(**sub_dependencies)
                    yielded_value = next(gen)
                    kwargs_to_pass[name] = yielded_value
                    context_managers.append(gen)
                else:
                    result = dep_func(**sub_dependencies)
                    kwargs_to_pass[name] = result

            request_cache[dep_func] = kwargs_to_pass[name]

        return kwargs_to_pass

    def run_request(self, path: str):
        print("incoming request")
        endpoint_fun = self.routes.get(path)
        if not endpoint_fun:
            print("no path found: 404")
            return

        request_cache = {}
        context_managers = []

        try:
            solved_kwargs = self._solve_dependencies(
                endpoint_fun, request_cache, context_managers
            )
            response = endpoint_fun(**solved_kwargs)
            print(f"status 200: {response}")
        finally:
            # execute context managers (tear down)
            for gen in reversed(context_managers):
                try:
                    next(gen, None)
                except StopIteration:
                    pass
        print("tear down complete")


# usage
app = Fastapi()


def get_db_connection():
    print("[dep] connecting to the database")
    db_conn = "postgres connection string"
    try:
        yield db_conn
    finally:
        print("closing the db")


def get_user_from_db(conn: str = Depends(get_db_connection)):
    print("fetching user with connection")
    return {"username": "zoya", "id": 100}


@app.get("/users/me")
def get_current_user_profile(user: dict = Depends(get_user_from_db)):
    return {"profile_data": f"Data for {user['username']}"}


app.run_request("/users/me")
