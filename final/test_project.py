import pytest
import project
import os
import csv
from project import get_message_detail
from unittest.mock import patch, Mock


def test_get_message_detail():
    with patch("project.get_message_detail") as mock_get_message:
        mock_get_message.return_value = project.message_detail
        assert project.get_message_detail().get("snippet") == "mock"


def test_update_order():
    with patch("project.get_message_detail") as mock_get_message:
        mock_get_message.return_value = project.message_detail
        project.update_order()
        assert os.path.exists("/workspaces/112750129/cs50p/final/order/mock") == True
        assert (
            os.path.isfile("/workspaces/112750129/cs50p/final/order/mock/mock.pdf")
            == True
        )


def test_remove_order():
    with open("/workspaces/112750129/cs50p/final/orders.csv", "a+") as file:
        writer = csv.writer(file)
        writer.writerow(["mock1", "1", "This is test remove 1", "n"])
        writer.writerow(["mock2", "2", "This is test remove 2", "y"])
    with open("/workspaces/112750129/cs50p/final/orders.csv", "r") as file:
        reader = csv.reader(file)
        reader = list(reader)
        last_row = reader[-1:]
        second_last_row = reader[-2:-1]
        assert last_row == [["mock2", "2", "This is test remove 2", "y"]]
        assert second_last_row == [["mock1", "1", "This is test remove 1", "n"]]
    if not os.path.exists("/workspaces/112750129/cs50p/final/order/mock1"):
        os.makedirs("/workspaces/112750129/cs50p/final/order/mock1")
    if not os.path.exists("/workspaces/112750129/cs50p/final/order/mock2"):
        os.makedirs("/workspaces/112750129/cs50p/final/order/mock2")
    project.remove_order()
    with open("/workspaces/112750129/cs50p/final/orders.csv", "r") as file:
        reader = csv.reader(file)
        reader = list(reader)
        last_row = reader[-1:]
        assert last_row == [["mock1", "1", "This is test remove 1", "n"]]
