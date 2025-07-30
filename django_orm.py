import sqlite3


class Field:
    """A descriptor representing a database column."""

    def __init__(self, db_type, primary_key=False):
        self.db_type = db_type
        self.primary_key = primary_key
        self._name = None  # will be set by the metaclass

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return None  # allow class level access example User.username

        return getattr(instance, self._name)

    def __set__(self, instance, value):
        setattr(instance, self._name, value)


class CharField(Field):
    def __init__(self, max_length=255, **kwargs):
        self.max_length = max_length
        super().__init__(f"VARCHAR({max_length})", **kwargs)


class IntegerField(Field):
    def __init__(self, **kwargs):
        super().__init__("INTEGER", **kwargs)


# the lazy queryset
class QuerySet:
    def __init__(self, model):
        self.model = model
        self._filters = []  # list of where clauses

    def _clone(self):
        cloned_qs = QuerySet(self.model)
        cloned_qs._filters = self._filters.copy()
        return cloned_qs

    def filter(self, **kwargs):
        cloned_qs = self._clone()
        cloned_qs._filters.append(kwargs)
        return cloned_qs

    def all(self):
        return self._clone()

    def _build_sql(self):
        """Constructs the SQL query from the model and filters"""
        table_name = self.model._meta.db_table
        fields = ", ".join(self.model._meta.fields.keys())
        sql = f"SELECT {fields} FROM {table_name}"

        if self._filters:
            where_clauses = []
            params = []
            for f in self._filters:
                for key, value in f.items():
                    where_clauses.append(f"{key} = ?")
                    params.append(value)

            sql += " WHERE " + " AND ".join(where_clauses)

        return sql, tuple(params)

    def __iter__(self):
        sql, params = self._build_sql()
        print(f"  [SQL] Executing: {sql} with params {params}")

        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # This is a mock execution, a real ORM would have the table
            # For this demo, we can't actually execute, so we yield mock objects

        if "id=1" in sql:
            obj = self.model(id=1, username="shaheer", email="shaheer@gmail.com")
            yield obj


class Manager:
    def __init__(self, model):
        self.model = model

    def get_queryset(self):
        return QuerySet(self.model)

    def __getattr__(self, name):
        return getattr(self.get_queryset(), name)


class ModelOptions:
    def __init__(self, meta_class_attrs):
        self.db_table = meta_class_attrs.get("db_table")
        self.fields = {}
        self.pk_field = None


class ModelMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        if name == "Model":
            return super().__new__(mcs, name, bases, attrs)

        # extract the fields from the class attributes
        fields = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Field):
                fields[attr_name] = attr_value
                attr_value.__set_name__(mcs, attr_name)

        # create the _meta options object
        meta_attrs = attrs.get("Meta", type("Meta", (), {}))
        opts = ModelOptions(meta_attrs.__dict__)
        opts.fields = fields
        opts.db_table = opts.db_table or name.lower() + "s"

        for field_name, field_obj in fields.items():
            if field_obj.primary_key:
                opts.pk_field = field_name

        attrs["_meta"] = opts

        # add the manager
        attrs["objects"] = Manager(model=None)

        new_class = super().__new__(mcs, name, bases, attrs)
        new_class.objects.model = (
            new_class  # give manager access to the newly created class
        )

        return new_class


class Model(metaclass=ModelMetaclass):
    """Base class for all models."""

    def __init__(self, **kwargs):
        for field_name in self._meta.fields:
            setattr(self, field_name, kwargs.get(field_name))

    def __repr__(self):
        field_values = {f: getattr(self, f) for f in self._meta.fields}
        return f"<{self.__class__.__name__}:{field_values}>"


class User(Model):
    id = IntegerField(primary_key=True)
    username = CharField(max_length=50)
    email = CharField(max_length=100)

    class Meta:
        db_table = "auth_user"  # Override default table name


print("ORM Introspection")
print(f"Model: {User}")
print(f"Table Name: {User._meta.db_table}")
print(f"Fields: {list(User._meta.fields.keys())}")
print(f"Primary Key: {User._meta.pk_field}")
print(f"Manager: {User.objects}")

# Querying: See the lazy QuerySet in action
print("Lazy QuerySet Demonstration")

# 1. This does NOT hit the database. It just creates a QuerySet object.
print("1. Creating a filtered QuerySet.")
users_qs = User.objects.filter(username="shaheer").filter(email="shaher@example.com")
print(f"   QuerySet object created: {users_qs}")

# 2. This STILL does not hit the database.
print("2. Chaining another filter ")
active_users_qs = users_qs.filter(id=1)
print(f"New QuerySet object created: {active_users_qs}")

# 3. NOW we hit the database, because we are iterating.
print("3. Iterating over the QuerySet to trigger DB query ")
for user in active_users_qs:
    print(f"   [ORM] Hydrated object: {user}")
