import os
import unittest
from werkzeug.test import create_environ
from werkzeug.wrappers import Request

from tests.test_web_base import TestWebBase
from hed import schema as hedschema
from hed.models import Sidecar, TabularInput
from hed.errors.exceptions import HedFileError
from constants import base_constants


class Test(TestWebBase):
    cache_schemas = True

    def test_get_input_from_events_form_empty(self):
        from events import get_events_form_input
        self.assertRaises(TypeError, get_events_form_input, {},
                          "An exception should be raised if an empty request is passed")
        self.assertTrue(1, "Testing get_events_form_input")

    def test_get_input_from_events_form(self):
        from hed.schema import HedSchema
        from events import get_events_form_input
        with self.app.test:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.json')
            events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
            with open(json_path, 'rb') as fp:
                with open(events_path, 'rb') as fpe:
                    environ = create_environ(data={base_constants.JSON_FILE: fp, base_constants.SCHEMA_VERSION: '8.0.0',
                                             base_constants.EVENTS_FILE: fpe, base_constants.EXPAND_DEFS: 'on',
                                             base_constants.COMMAND_OPTION: base_constants.COMMAND_ASSEMBLE})
            request = Request(environ)
            arguments = get_events_form_input(request)
            self.assertIsInstance(arguments[base_constants.EVENTS], TabularInput,
                                  "get_events_form_input should have an events object")
            self.assertIsInstance(arguments[base_constants.SCHEMA], HedSchema,
                                  "get_events_form_input should have a HED schema")
            self.assertEqual(base_constants.COMMAND_ASSEMBLE, arguments[base_constants.COMMAND],
                             "get_events_form_input should have a command")
            self.assertTrue(arguments[base_constants.EXPAND_DEFS],
                            "get_events_form_input should have expand_defs true when on")

    def test_events_process_empty_file(self):
        # Test for empty events_path
        from events import process
        arguments = {'events_path': ''}
        try:
            process(arguments)
        except HedFileError:
            pass
        except Exception as ex:
            self.fail(f'process threw the wrong exception {str(ex)} when events_path was empty')
        else:
            self.fail('process should have thrown a HedFileError exception when events_path was empty')

    def test_events_process_invalid(self):
        from events import process
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events_bad.json')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)
        json_sidecar = Sidecar(file=json_path, name='bids_events_bad')
        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        arguments = {base_constants.EVENTS: events, base_constants.COMMAND: base_constants.COMMAND_VALIDATE,
                     base_constants.EXPAND_DEFS: True,
                     base_constants.CHECK_FOR_WARNINGS: True, base_constants.SCHEMA: hed_schema}
        with self.app.app_context():
            results = process(arguments)
            self.assertTrue(isinstance(results, dict),
                            'process validation should return a result dictionary when validation errors')
            self.assertEqual('warning', results['msg_category'],
                             'process validate should return warning when errors')

    def test_events_process_valid(self):
        from events import process
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.json')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)
        json_sidecar = Sidecar(file=json_path, name='bids_json')
        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        arguments = {base_constants.EVENTS: events, base_constants.COMMAND: base_constants.COMMAND_VALIDATE,
                     base_constants.EXPAND_DEFS: True,
                     base_constants.CHECK_FOR_WARNINGS: True, base_constants.SCHEMA: hed_schema}
        with self.app.app_context():
            results = process(arguments)
            self.assertTrue(isinstance(results, dict),
                            'process validation should return a dictionary when validation errors')
            self.assertEqual('success', results['msg_category'],
                             'process validate should give success when no errors')
            self.assertFalse(results["data"], 'process not return data no no errors')

    def test_events_assemble_invalid(self):
        from events import assemble
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events_bad.json')
        json_sidecar = Sidecar(file=json_path, name='bids_events_bad')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)

        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        with self.app.app_context():
            results = assemble(hed_schema, events,  expand_defs=True)
            self.assertTrue('data' in results,
                            'assemble results should have a data key when no errors')
            self.assertEqual('warning', results["msg_category"],
                             'assemble msg_category should be warning when errors')

    def test_events_assemble_valid(self):
        from events import assemble
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.json')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)
        json_sidecar = Sidecar(file=json_path, name='bids_json')
        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        with self.app.app_context():
            results = assemble(hed_schema, events, expand_defs=True)
            self.assertTrue(results['data'],
                            'assemble results should have a data key when no errors')
            self.assertEqual('success', results['msg_category'],
                             'assemble msg_category should be success when no errors')

    def test_generate_sidecar_invalid(self):
        from events import generate_sidecar
        with self.app.app_context():
            try:
                results = generate_sidecar(None, columns_selected={'event_type': True})
            except AttributeError:
                pass
            except Exception as ex:
                self.fail(f"generate_sidecar threw {type(ex).__name__} for missing EventInput")
            else:
                self.fail('generate_sidecar should throw HedFileError when EventInput is None')

    def test_generate_sidecar_valid(self):
        from events import generate_sidecar
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        events = TabularInput(file=events_path, name='bids_events')
        results = generate_sidecar(events,
                                   columns_selected={'event_type': True, 'bci_prediction': True, 'trial': False})

        self.assertTrue(results['data'],
                        'generate_sidecar results should have a data key when no errors')
        self.assertEqual('success', results['msg_category'],
                         'generate_sidecar msg_category should be success when no errors')

    def test_search_invalid(self):
        from events import search
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.json')
        json_sidecar = Sidecar(file=json_path, name='bids_sidecar')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)

        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        with self.app.app_context():
            results = search(hed_schema, events, query="")
            self.assertTrue('data' in results, 'make_query results should have a data key when errors')
            self.assertEqual('warning', results["msg_category"],
                             'make_query msg_category should be warning when errors')

    def test_events_search_valid(self):
        from events import search
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.json')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)
        json_sidecar = Sidecar(file=json_path, name='bids_json')
        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        with self.app.app_context():
            results = search(hed_schema, events, query="Sensory-event")
            self.assertTrue(results['data'],
                            'make_query results should have a data key when no errors')
            self.assertEqual('success', results['msg_category'],
                             'make_query msg_category should be success when no errors')

    def test_events_validate_invalid(self):
        from events import validate
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events_bad.json')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)
        json_sidecar = Sidecar(file=json_path, name='bids_events_bad')
        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        with self.app.app_context():
            results = validate(hed_schema, events)
            self.assertTrue(results['data'],
                            'validate results should have a data key when validation errors')
            self.assertEqual('warning', results["msg_category"],
                             'validate msg_category should be warning when errors')

    def test_events_validate_valid(self):
        from events import validate
        events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.tsv')
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/bids_events.json')
        json_sidecar = Sidecar(file=json_path, name='bids_events')
        events = TabularInput(file=events_path, sidecar=json_sidecar, name='bids_events')
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/HED8.0.0.xml')
        hed_schema = hedschema.load_schema(schema_path)

        with self.app.app_context():
            results = validate(hed_schema, events)
            self.assertFalse(results['data'],
                             'validate results should not have a data key when no validation errors')
            self.assertEqual('success', results['msg_category'],
                             'validate msg_category should be success when no errors')


if __name__ == '__main__':
    unittest.main()
