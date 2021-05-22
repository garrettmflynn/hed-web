from flask import current_app
from werkzeug import Response
import pandas as pd

from hed.util.error_reporter import get_printable_issue_string
from hed.util.event_file_input import EventFileInput
from hed.util.exceptions import HedFileError
from hed.util.column_def_group import ColumnDefGroup
from hed.validator.hed_validator import HedValidator
from hedweb.constants import common, file_constants
from hedweb.dictionary import dictionary_validate
from hed.schema.hed_schema_file import load_schema
from hedweb.web_utils import form_has_option, generate_response_download_file_from_text,\
    generate_filename, generate_text_response, get_events_file, get_hed_schema, get_json_dictionary, \
    get_hed_path_from_pull_down, get_uploaded_file_path_from_form
app_config = current_app.config


def generate_input_from_events_form(request):
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
    hed_file_path, schema_display_name = get_hed_path_from_pull_down(request)
    uploaded_events_path, original_events_name = \
        get_uploaded_file_path_from_form(request, common.EVENTS_FILE, file_constants.TEXT_FILE_EXTENSIONS)
    uploaded_json_name, original_json_name = \
        get_uploaded_file_path_from_form(request, common.JSON_FILE, file_constants.DICTIONARY_FILE_EXTENSIONS)

    arguments = {
        common.SCHEMA_PATH: hed_file_path,
        common.SCHEMA_DISPLAY_NAME: schema_display_name,
        common.EVENTS_PATH: uploaded_events_path,
        common.EVENTS_FILE: original_events_name,
        common.EVENTS_DISPLAY_NAME: original_events_name,
        common.JSON_PATH: uploaded_json_name,
        common.JSON_DISPLAY_NAME: original_json_name,
    }
    if form_has_option(request, common.COMMAND_OPTION, common.COMMAND_VALIDATE):
        arguments[common.COMMAND] = common.COMMAND_VALIDATE
    elif form_has_option(request, common.COMMAND_OPTION, common.COMMAND_ASSEMBLE):
        arguments[common.COMMAND] = common.COMMAND_ASSEMBLE
    else:
        arguments[common.COMMAND] = ''
    return arguments


def events_process(arguments):
    """Perform the requested action for the dictionary.

    Parameters
    ----------
    arguments: dict
        A dictionary with the input arguments from the dictionary form

    Returns
    -------
      Response
        Downloadable response object.
    """
    if common.COMMAND not in arguments:
        raise HedFileError('MissingCommand', 'Command is missing', '')
    elif arguments['command'] == common.COMMAND_VALIDATE:
        results = events_validate(arguments)
    elif arguments['command'] == common.COMMAND_ASSEMBLE:
        results = events_assemble(arguments)
    else:
        raise HedFileError('UnknownProcessingMethod', 'Select an events file processing method', '')
    msg = results.get('msg', '')
    category = results.get('msg_category', 'success')

    if results['data']:
        display_name = results.get('events_display_name', '')
        return generate_response_download_file_from_text(results['data'], display_name=display_name,
                                                         msg_category=category, msg=msg)
    else:
        return generate_text_response('', msg=msg, msg_category=category)


def events_assemble(arguments, hed_schema=None):
    """Converts an events file from short to long unless short_to_long is set to False, then long_to_short

    Parameters
    ----------
    arguments: dict
        Dictionary containing standard input form arguments
    hed_schema:str or HedSchema
        Version number or path or HedSchema object to be used

    Returns
    -------
    dict
        A dictionary pointing to assembled string or errors
    """

    if not hed_schema:
        hed_schema = get_hed_schema(arguments)
    json_dictionary = get_json_dictionary(arguments, json_optional=True)
    def_dicts = json_dictionary.extract_defs()
    events_file = get_events_file(arguments, json_dictionary=json_dictionary, def_dicts=def_dicts)
    results = events_validate(arguments, hed_schema=hed_schema, events_file=events_file)
    if results['data']:
        return results
    hed_tags = []
    onsets = []
    for row_number, row_dict in events_file.parse_dataframe(return_row_dict=True):
        hed1 = row_dict["HED"]
        hed = str(row_dict.get("HED", ""))
        print(hed)
        hed_tags.append(str(row_dict.get("HED", "")))
        onsets.append(row_dict.get("onset", "n/a"))
    data = {'onset': onsets, 'HED': hed_tags}
    df = pd.DataFrame(data)
    csv_string = df.to_csv(None, sep='\t', index=False, header=True)
    file_name = generate_filename(common.EVENTS_FILE, suffix='_expanded', extension='.tsv')
    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    return {'command': arguments.get('command', ''), 'data': csv_string, 'output_display_name': file_name,
            'schema_version': schema_version, 'msg_category': 'success',
            'msg': 'Events file successfully expanded'}


def events_validate(arguments, hed_schema=None, events_file=None):
    """Reports the spreadsheet validation status.

    Parameters
    ----------
    arguments: dict
        A dictionary of the values extracted from the form
    hed_schema: str or HedSchema
        Version number or path or HedSchema object to be used
    events_file: EventFileInput
        Event file object passed in from elsewhere

    Returns
    -------
    dict
         A dictionary containing pointer to file with validation errors or a message
    """

    if not hed_schema:
        hed_schema = get_hed_schema(arguments)
    if not events_file:
        json_dictionary = get_json_dictionary(arguments, json_optional=True)
        def_dicts = None
        if json_dictionary:
            results = dictionary_validate(arguments, hed_schema=hed_schema, json_dictionary=json_dictionary)
            if results['data']:
                return results
            def_dicts = json_dictionary.extract_defs()

        events_file = get_events_file(arguments, json_dictionary=json_dictionary, def_dicts=def_dicts)
    schema_version = hed_schema.header_attributes.get('version', 'Unknown version')
    validator = HedValidator(hed_schema=hed_schema)
    issues = validator.validate_input(events_file)
    if issues:
        display_name = arguments.get(common.EVENTS_FILE, None)
        issue_str = get_printable_issue_string(issues, f"{display_name} HED validation errors")

        file_name = generate_filename(display_name, suffix='_validation_errors', extension='.txt')
        return {'command': arguments.get('command', ''), 'data': issue_str, "output_display_name": file_name,
                'schema_version': schema_version, "msg_category": "warning",
                'msg': "Events file had validation errors"}
    else:
        return {'command': arguments.get('command', ''), 'data': '',
                'schema_version': schema_version, 'msg_category': 'success',
                'msg': 'Events file had no validation errors'}
