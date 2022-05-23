from flask import current_app
import json
from werkzeug.utils import secure_filename
import pandas as pd

from hed.models import Sidecar, TabularInput
from hed import schema as hedschema
from hed.errors import get_printable_issue_string, HedFileError
from hed.validator import HedValidator
from constants import base_constants
from columns import create_column_selections, create_columns_included
from hed.util import generate_filename
from hed.tools import BidsTabularSummary, assemble_hed, generate_sidecar_entry, search_tabular
from web_util import form_has_option, get_hed_schema_from_pull_down

app_config = current_app.config


def get_events_form_input(request):
    """ Extract a dictionary of input for processing from the events form.

    Args:
        request (Request): A Request object containing user data from the validation form.

    Returns:
        dict: A dictionary of events processing parameters in standard form.

    """

    arguments = {base_constants.SCHEMA: None,
                 base_constants.EVENTS: None,
                 base_constants.COMMAND: request.form.get(base_constants.COMMAND_OPTION, ''),
                 base_constants.CHECK_FOR_WARNINGS: form_has_option(request, base_constants.CHECK_FOR_WARNINGS, 'on'),
                 base_constants.EXPAND_DEFS: form_has_option(request, base_constants.EXPAND_DEFS, 'on'),
                 base_constants.COLUMNS_SELECTED: create_column_selections(request.form),
                 base_constants.COLUMNS_INCLUDED: create_columns_included(request.form)
                 }
    if arguments[base_constants.COMMAND] == base_constants.COMMAND_ASSEMBLE:
        arguments[base_constants.COLUMNS_INCLUDED] = ['onset']   # TODO  add user interface option to choose columns.
    if arguments[base_constants.COMMAND] != base_constants.COMMAND_GENERATE_SIDECAR:
        arguments[base_constants.SCHEMA] = get_hed_schema_from_pull_down(request)
    json_sidecar = None
    if base_constants.JSON_FILE in request.files:
        f = request.files[base_constants.JSON_FILE]
        json_sidecar = Sidecar(file=f, name=secure_filename(f.filename))
    arguments[base_constants.JSON_SIDECAR] = json_sidecar
    if base_constants.EVENTS_FILE in request.files:
        f = request.files[base_constants.EVENTS_FILE]
        arguments[base_constants.EVENTS] = \
            TabularInput(file=f, sidecar=arguments.get(base_constants.JSON_SIDECAR, None),
                         name=secure_filename(f.filename))
    return arguments


def process(arguments):
    """ Perform the requested action for the events file and its sidecar.

    Args:
        arguments (dict): A dictionary with the input arguments from the event form or service request.

    Returns:
        dict: A dictionary of results in the standard results format.

    Raises:
        HedFileError:  If the command was not found or the input arguments were not valid.

    """
    hed_schema = arguments.get('schema', None)
    command = arguments.get(base_constants.COMMAND, None)
    if command == base_constants.COMMAND_GENERATE_SIDECAR:
        pass
    elif not hed_schema or not isinstance(hed_schema, hedschema.hed_schema.HedSchema):
        raise HedFileError('BadHedSchema', "Please provide a valid HedSchema for event processing", "")
    events = arguments.get(base_constants.EVENTS, None)
    sidecar = arguments.get(base_constants.JSON_SIDECAR, None)
    query = arguments.get(base_constants.QUERY, None)
    columns_included = arguments.get(base_constants.COLUMNS_INCLUDED, None)
    if not events or not isinstance(events, TabularInput):
        raise HedFileError('InvalidEventsFile', "An events file was given but could not be processed", "")
    if command == base_constants.COMMAND_VALIDATE:
        results = validate(hed_schema, events, sidecar, arguments.get(base_constants.CHECK_FOR_WARNINGS, False))
    elif command == base_constants.COMMAND_SEARCH:
        results = search(hed_schema, events, query, columns_included=columns_included)
    elif command == base_constants.COMMAND_ASSEMBLE:
        results = assemble(hed_schema, events,
                           arguments.get(base_constants.COLUMNS_INCLUDED, None),
                           arguments.get(base_constants.EXPAND_DEFS, False))
    elif command == base_constants.COMMAND_GENERATE_SIDECAR:
        results = generate_sidecar(events, arguments.get(base_constants.COLUMNS_SELECTED, None))
    else:
        raise HedFileError('UnknownEventsProcessingMethod', f'Command {command} is missing or invalid', '')
    return results


def assemble(hed_schema, events, columns_included=None, expand_defs=True):
    """ Create a tabular file with the first column, specified additional columns and a HED column.

    Args:
        hed_schema (HedSchema or HedSchemaGroup): A HED schema or HED schema group.
        events (TabularInput):  An tabular input object.
        columns_included (dict): Optional dictionary of columns to include in the assembled output.
        expand_defs (bool): True if definitions should be expanded during assembly.

    Returns:
        dict: A dictionary of results in standard format including either the assembled events string or errors.

    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    results = validate(hed_schema, events)
    if results['data']:
        return results
    df = assemble_hed(events, columns_included=columns_included, expand_defs=expand_defs)
    csv_string = df.to_csv(None, sep='\t', index=False, header=True)
    display_name = events.name
    file_name = generate_filename(display_name, name_suffix='_expanded', extension='.tsv')
    return {base_constants.COMMAND: base_constants.COMMAND_ASSEMBLE,
            base_constants.COMMAND_TARGET: 'events',
            'data': csv_string, 'output_display_name': file_name,
            'schema_version': schema_version, 'msg_category': 'success', 'msg': 'Events file successfully expanded'}


def generate_sidecar(events, columns_selected):
    """ Generate a JSON sidecar template from a BIDS-style events file.

    Args:
        events (EventInput):      An events input object to generate sidecars from.
        columns_selected (dict):  A dictionary of columns selected.

    Returns:
        dict: A dictionary of results in standard format including either the generated sidecar string or errors.

    """

    columns_info = BidsTabularSummary.get_columns_info(events.dataframe)
    hed_dict = {}
    for column_name, column_type in columns_selected.items():
        if column_name not in columns_info:
            continue
        if column_type:
            column_values = list(columns_info[column_name].keys())
        else:
            column_values = None
        hed_dict[column_name] = generate_sidecar_entry(column_name, column_values=column_values)
    display_name = events.name

    file_name = generate_filename(display_name, name_suffix='_generated', extension='.json')
    return {base_constants.COMMAND: base_constants.COMMAND_GENERATE_SIDECAR,
            base_constants.COMMAND_TARGET: 'events',
            'data': json.dumps(hed_dict, indent=4),
            'output_display_name': file_name, 'msg_category': 'success',
            'msg': 'JSON sidecar generation from event file complete'}


def search(hed_schema, events, query, columns_included=None):
    """ Create a three-column tsv file with event number, matched string, and assembled strings for matched events.

    Args:
        hed_schema (HedSchema or HedSchemaGroup): A HED schema or HED schema group.
        events (EventsInput):     An events input object.
        query (str):              A string containing the query.
        columns_included (list):  A list of column names of columns to include.

    Returns:
        dict: A dictionary pointing to results or errors.

    """
    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    results = validate(hed_schema, events)
    if results['data']:
        return results
    results = validate_query(hed_schema, query)
    if results['data']:
        return results

    df = search_tabular(events, hed_schema, query, columns_included=columns_included)
    if isinstance(df, pd.DataFrame):
        csv_string = df.to_csv(None, sep='\t', index=False, header=True)
        msg = f"Events file query {query} satisfied by {len(df)} out of {len(events.dataframe)} events."
    else:
        csv_string = ''
        msg = f"Events file has no events satisfying the query {query}."
    display_name = events.name
    file_name = generate_filename(display_name, name_suffix='_query', extension='.tsv')
    return {base_constants.COMMAND: base_constants.COMMAND_SEARCH,
            base_constants.COMMAND_TARGET: 'events',
            'data': csv_string, 'output_display_name': file_name,
            'schema_version': schema_version, 'msg_category': 'success', 'msg': msg}


def validate(hed_schema, events, sidecar=None, check_for_warnings=False):
    """ Validate a tabular input object and return the results.

    Args:
        hed_schema (HedSchema or HedSchemaGroup): Schema or schemas used for validation.
        events (TabularInput): Tabular input object representing a file to be validated.
        sidecar (Sidecar or None): The Sidecar associated with this tabular data file.
        check_for_warnings (bool): If true, validation should include warnings.

    Returns:
        dict: A dictionary containing results of validation in standard format.

    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    display_name = events.name
    validator = HedValidator(hed_schema=hed_schema)
    issue_str = ''
    if sidecar:
        issues = sidecar.validate_entries(validator, check_for_warnings=check_for_warnings)
        if issues:
            issue_str = issue_str + get_printable_issue_string(issues, title="Sidecar definition errors:")
    if not issue_str:
        issues = events.validate_file(validator, check_for_warnings=check_for_warnings)
        if issues:
            issue_str = get_printable_issue_string(issues, title="Event file errors:")

    if issue_str:
        file_name = generate_filename(display_name, name_suffix='_validation_errors', extension='.txt')
        return {base_constants.COMMAND: base_constants.COMMAND_VALIDATE,
                base_constants.COMMAND_TARGET: 'events',
                'data': issue_str, "output_display_name": file_name,
                base_constants.SCHEMA_VERSION: schema_version, "msg_category": "warning",
                'msg': f"Events file {display_name} had validation errors"}
    else:
        return {base_constants.COMMAND: base_constants.COMMAND_VALIDATE,
                base_constants.COMMAND_TARGET: 'sidecar', 'data': '',
                base_constants.SCHEMA_VERSION: schema_version, 'msg_category': 'success',
                'msg': f"Events file {display_name} had no validation errors"}


def validate_query(hed_schema, query):
    """ Validate the query and return the results.

    Args:
        hed_schema (HedSchema, or HedSchemaGroup): Schema or schemas used to validate the query.
        query (str):  A str representing the query.

    Returns
        dict: A dictionary containing results of validation in standard format.

    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    if not query:
        display_name = 'empty_query'
        issue_str = "Empty query could not be processed."
        file_name = generate_filename(display_name, name_suffix='_validation_errors', extension='.txt')
        return {base_constants.COMMAND: base_constants.COMMAND_VALIDATE,
                base_constants.COMMAND_TARGET: 'query',
                'data': issue_str, "output_display_name": file_name,
                base_constants.SCHEMA_VERSION: schema_version, "msg_category": "warning",
                'msg': f"Query {display_name} had validation errors"}
    else:
        display_name = 'Nice_query'
        return {base_constants.COMMAND: base_constants.COMMAND_VALIDATE,
                base_constants.COMMAND_TARGET: 'query', 'data': '',
                base_constants.SCHEMA_VERSION: schema_version, 'msg_category': 'success',
                'msg': f"Events file {display_name} had no validation errors"}
