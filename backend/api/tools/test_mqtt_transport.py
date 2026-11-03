"""Dependency-free tests of production transport, with a fake MQTT network."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class FakeClient:
    scenario = "ok"
    last = None

    def __init__(self, *args, **kwargs):
        FakeClient.last = self
        self.subscribed = False
        self.stopped = False
        self.publications = []

    def connect(self, *args, **kwargs):
        if self.scenario == "offline":
            raise OSError("offline")

    def loop_start(self):
        self.on_connect(self, None, None, SimpleNamespace(is_failure=False), None)

    def subscribe(self, topic, qos):
        self.topic = topic
        return (0, 1)

    def loop_suback(self):
        self.subscribed = True
        self.on_subscribe(self, None, 1, [SimpleNamespace(is_failure=False)], None)

    def publish(self, topic, payload, qos, retain):
        assert self.subscribed, "published before SUBACK"
        self.publications.append((topic, json.loads(payload), qos, retain))
        ack = json.loads(payload)
        ack["status"] = "rejected" if self.scenario == "rejected" else "applied"
        if self.scenario == "wrong_id": ack["command_id"] = "other"
        if self.scenario == "wrong_state": ack["state"] = not ack["state"]
        if self.scenario == "wrong_type": ack["state"] = int(ack["state"])
        if self.scenario == "wrong_actuator": ack["actuator"] = "pump"
        if self.scenario != "silent":
            self.on_message(self, None, SimpleNamespace(payload=json.dumps(ack).encode(), retain=self.scenario == "retained"))
        return SimpleNamespace(rc=0)

    def disconnect(self): pass
    def loop_stop(self): self.stopped = True
    def username_pw_set(self, *args): pass
    def tls_set(self): pass


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(MQTT_ENABLED=True, MQTT_HOST="broker", MQTT_PORT=1883,
            MQTT_USERNAME="", MQTT_PASSWORD="", MQTT_TLS=False,
            MQTT_DEVICE_ID="field_esp32", MQTT_TOPIC_PREFIX="invernadero", MQTT_TIMEOUT_SECONDS=0.001)
        mqtt = ModuleType("paho.mqtt.client")
        mqtt.Client = FakeClient
        mqtt.CallbackAPIVersion = SimpleNamespace(VERSION2=2)
        mqtt.MQTT_ERR_SUCCESS = 0
        paho = ModuleType("paho"); paho.__path__ = []
        package = ModuleType("paho.mqtt"); package.__path__ = []; package.client = mqtt; paho.mqtt = package
        config = ModuleType("app.config"); config.settings = self.settings
        app = ModuleType("app"); app.__path__ = []
        modules = {"paho": paho, "paho.mqtt": package, "paho.mqtt.client": mqtt, "app": app, "app.config": config}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("transport_under_test", Path(__file__).parents[1] / "app/mqtt_commands.py")
            self.transport = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.transport)
        FakeClient.scenario = "ok"
        # Model asynchronous SUBACK occurring after subscribe() has returned.
        original = FakeClient.loop_start
        self.start = patch.object(FakeClient, "loop_start", lambda client: (original(client), client.loop_suback()))
        self.start.start()
        self.addCleanup(self.start.stop)

    def test_on_off_ack_and_topics(self):
        for state in (True, False):
            ack = self.transport.send_command("fan_1", state)
            self.assertIs(ack["state"], state)
            client = FakeClient.last
            self.assertEqual(client.topic, "invernadero/field_esp32/ack")
            topic, command, qos, retain = client.publications[0]
            self.assertEqual(topic, "invernadero/field_esp32/command")
            self.assertEqual(len(command["command_id"]), 36)
            self.assertEqual(qos, 1)
            self.assertFalse(retain)
            self.assertTrue(client.stopped)

    def test_no_false_success(self):
        for scenario in ("wrong_id", "wrong_state", "wrong_type", "wrong_actuator", "retained", "silent"):
            with self.subTest(scenario=scenario):
                FakeClient.scenario = scenario
                with self.assertRaises(self.transport.CommandTimeout):
                    self.transport.send_command("fan_1", True)
                self.assertTrue(FakeClient.last.stopped)

    def test_rejected(self):
        FakeClient.scenario = "rejected"
        with self.assertRaises(self.transport.CommandRejected):
            self.transport.send_command("pump", True)

    def test_disabled(self):
        self.settings.MQTT_ENABLED = False
        with self.assertRaises(self.transport.CommandUnavailable):
            self.transport.send_command("fan_1", True)

    def test_broker_offline(self):
        FakeClient.scenario = "offline"
        with self.assertRaises(self.transport.CommandUnavailable):
            self.transport.send_command("fan_1", True)
        self.assertTrue(FakeClient.last.stopped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
