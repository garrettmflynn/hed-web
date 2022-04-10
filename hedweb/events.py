from flask import current_app
import json
from werkzeug.utils import secure_filename
import pandas as pd

from hed import models
from hed import schema as hedschema
from hed.errors import get_printable_issue_string, HedFileError
from hed.validator import HedValidator
from hedweb.constants import base_constants
from hedweb.columns import create_column_selections
from hed.util import generate_filename
from hed.tools import generate_sidecar_entry, BidsTsvSummary
from hedweb.web_util import form_has_option, get_hed_schema_from_pull_down

app_config = current_app.config


def get_input_from_events_form(request):
    """Gets the validation function input arguments from a request object associated with the validation form.

    Parameters
    ----------
    request: Request object
        A Request object containing user data from the validation form.

    Returns
    -------
    dictionary
        A dictionary containing input arguments for calling the underlying validation function.
    """

    arguments = {base_constants.SCHEMA: None,
                 base_constants.EVENTS: None,
                 base_constants.COMMAND: request.form.get(base_constants.COMMAND_OPTION, ''),
                 base_constants.CHECK_FOR_WARNINGS: form_has_option(request, base_constants.CHECK_FOR_WARNINGS, 'on'),
                 base_constants.EXPAND_DEFS: form_has_option(request, base_constants.EXPAND_DEFS, 'on'),
                 base_constants.COLUMNS_SELECTED: create_column_selections(request.form)
                 }
    if arguments[base_constants.COMMAND] != base_constants.COMMAND_GENERATE_SIDECAR:
        arguments[base_constants.SCHEMA] = get_hed_schema_from_pull_down(request)
    json_sidecar = None
    if base_constants.JSON_FILE in request.files:
        f = request.files[base_constants.JSON_FILE]
        json_sidecar = models.Sidecar(file=f, name=secure_filename(f.filename))
    arguments[base_constants.JSON_SIDECAR] = json_sidecar
    if base_constants.EVENTS_FILE in request.files:
        f = request.files[base_constants.EVENTS_FILE]
        arguments[base_constants.EVENTS] = \
            models.EventsInput(file=f, sidecars=json_sidecar, name=secure_filename(f.filename))
    return arguments


def process(arguments):
    """Perform the requested action for the events file and its sidecar

    Parameters
    ----------
    arguments: dict
        A dictionary with the input arguments from the event form

    Returns
    -------
      dict
        A dictionary with the results.
    """
    hed_schema = arguments.get('schema', None)
    command = arguments.get(base_constants.COMMAND, None)
    if command == base_constants.COMMAND_GENERATE_SIDECAR:
        pass
    elif not hed_schema or not isinstance(hed_schema, hedschema.hed_schema.HedSchema):
        raise HedFileError('BadHedSchema', "Please provide a valid HedSchema for event processing", "")
    events = arguments.get(base_constants.EVENTS, None)
    sidecar = arguments.get(base_constants.JSON_SIDECAR, None)
    if not events or not isinstance(events, models.EventsInput):
        raise HedFileError('InvalidEventsFile', "An events file was given but could not be processed", "")
    if command == base_constants.COMMAND_VALIDATE:
        results = validate(hed_schema, events, sidecar, arguments.get(base_constants.CHECK_FOR_WARNINGS, False))
    elif command == base_constants.COMMAND_ASSEMBLE:
        results = assemble(hed_schema, events, arguments.get(base_constants.EXPAND_DEFS, False))
    elif command == base_constants.COMMAND_GENERATE_SIDECAR:
        results = generate_sidecar(events, arguments.get(base_constants.COLUMNS_SELECTED, None))
    else:
        raise HedFileError('UnknownEventsProcessingMethod', f'Command {command} is missing or invalid', '')
    return results


def assemble(hed_schema, events, expand_defs=True):
    """Creates a two-column event file with first column Onset and second column HED tags.

    Parameters
    ----------
    hed_schema: HedSchema
        A HED schema
    events: model.EventsInput
        An events input object
    expand_defs: bool
        True if definitions should be expanded during assembly
    Returns
    -------
    dict
        A dictionary pointing to assembled string or errors
    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    results = validate(hed_schema, events)
    if results['data']:
        return results

    hed_tags = []
    onsets = []
    for row_number, row_dict in events.iter_dataframe(return_row_dict=True, expand_defs=expand_defs,
                                                      remove_definitions=True):
        hed_tags.append(str(row_dict.get("HED", "")))
        onsets.append(row_dict.get("onset", "n/a"))
    data = {'onset': onsets, 'HED': hed_tags}
    df = pd.DataFrame(data)
    csv_string = df.to_csv(None, sep='\t', index=False, header=True)
    display_name = events.name
    file_name = generate_filename(display_name, name_suffix='_expanded', extension='.tsv')
    return {base_constants.COMMAND: base_constants.COMMAND_ASSEMBLE,
            base_constants.COMMAND_TARGET: 'events',
            'data': csv_string, 'output_display_name': file_name,
            'schema_version': schema_version, 'msg_category': 'success', 'msg': 'Events file successfully expanded'}


def generate_sidecar(events, columns_selected):
    """Generate a JSON sidecar template from a BIDS-style events file.

    Parameters
    ----------
    events: EventInput
        An events input object
    columns_selected: dict
        dictionary of columns selected

    Returns
    -------
    dict
        A dictionary pointing to extracted JSON file.
    """

    columns_info = BidsTsvSummary.get_columns_info(events.dataframe)
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


def validate(hed_schema, events, sidecar=None, check_for_warnings=False):
    """Validates and events input object and returns the results.

    Parameters
    ----------
    hed_schema: str or HedSchema
        Version number or path or HedSchema object to be used
    events: EventsInput
        Events input object to be validated
    sidecar: Sidecar
        Representation of a BIDS JSON sidecar object
    check_for_warnings: bool
        If true, validation should include warnings

    Returns
    -------
    dict
         A dictionary containing results of validation in standard format
    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    display_name = events.name
    validator = HedValidator(hed_schema=hed_schema)
    issue_str = ''
    if sidecar:
        issues = sidecar.validate_entries(validator, check_for_warnings=check_for_warnings)
        if issues:
            issue_str = issue_str + get_printable_issue_string(issues, title="Sidecar definition errors:")
    issues = events.validate_file(validator, check_for_warnings=check_for_warnings)
    if issues:
        issue_str = issue_str + get_printable_issue_string(issues, title="Event file errors:")

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
