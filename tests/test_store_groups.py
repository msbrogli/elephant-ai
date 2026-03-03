"""Tests for Group CRUD in DataStore."""

import os

from elephant.data.models import Group
from elephant.data.store import DataStore


class TestGroups:
    def test_write_and_read_group(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        group = Group(group_id="close-friends", display_name="Close Friends", color="#e91e8c")
        path = store.write_group(group)
        assert os.path.exists(path)
        assert path.endswith("close-friends.yaml")

        loaded = store.read_group("close-friends")
        assert loaded is not None
        assert loaded.display_name == "Close Friends"
        assert loaded.color == "#e91e8c"

    def test_read_group_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.read_group("nonexistent") is None

    def test_read_all_groups(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        store.write_group(Group(group_id="bjj", display_name="BJJ Training"))
        store.write_group(
            Group(group_id="close-friends", display_name="Close Friends", color="#e91e8c"),
        )

        groups = store.read_all_groups()
        assert len(groups) == 2
        ids = {g.group_id for g in groups}
        assert ids == {"bjj", "close-friends"}

    def test_read_all_groups_empty(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.read_all_groups() == []

    def test_delete_group(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        store.write_group(Group(group_id="test", display_name="Test"))
        assert store.delete_group("test") is True
        assert store.read_group("test") is None

    def test_delete_group_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.delete_group("nonexistent") is False

    def test_group_without_color(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        group = Group(group_id="college", display_name="College Friends")
        store.write_group(group)

        loaded = store.read_group("college")
        assert loaded is not None
        assert loaded.color is None

    def test_initialize_creates_groups_dir(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert os.path.isdir(os.path.join(data_dir, "groups"))
