import os
import io
import json
from flask import current_app
from hed.models import HedString, Sidecar, SpreadsheetInput, TabularInput
from hed.errors import HedFileError
from hed import schema as hedschema
from constants import base_constants
import events, spreadsheet, sidecar, strings


app_config = current_app.config


def get_input_from_request(request):
    """ Get a dictionary of input from a service request.

    Args:
        request (Request): A Request object containing user data for the service request.

    Returns:
        dict: A dictionary containing input arguments for calling the service request.

    """

    form_data = request.data
    form_string = form_data.decode()
    service_request = json.loads(form_string)
    arguments = get_service_info(service_request)
    arguments[base_constants.SCHEMA] = get_input_schema(service_request)
    get_column_parameters(arguments, service_request)
    get_sidecar(arguments, service_request)
    get_input_objects(arguments, service_request)
    arguments[base_constants.QUERY] = service_request.get('query', None)
    return arguments


def get_column_parameters(arguments, params):
    """ Update arguments with the columns that requested for the service.

    Args:
        arguments (dict):  A dictionary with the extracted parameters that are to be processed.
        params (dict): The service request dictionary extracted from the Request object.

    Updates the arguments dictionary with the column information in service_request.

    """

    columns_selected = {}
    if 'columns_categorical' in params:
        for column in params['columns_categorical']:
            columns_selected[column] = True
    if 'columns_value' in params:
        for column in params['columns_value']:
            columns_selected[column] = False
    arguments[base_constants.COLUMNS_SELECTED] = columns_selected
    columns_included = []
    if 'columns_included' in params:
        for column in params['columns_included']:
            columns_included.append(column)
    arguments[base_constants.COLUMNS_INCLUDED] = columns_included


def get_sidecar(arguments, params):
    """ Update arguments with the sidecars if there are any.

     Args:
         arguments (dict):  A dictionary with the extracted parameters that are to be processed.
         params (dict): The service request dictionary extracted from the Request object.

     Updates the arguments dictionary with the sidecars.

     """
    sidecar_str = ''
    if base_constants.JSON_STRING in params and params[base_constants.JSON_STRING]:
        sidecar_str = params[base_constants.JSON_STRING]
    elif base_constants.JSON_LIST in params and params[base_constants.JSON_LIST]:
        merged_sidecar = {}
        for s_string in params[base_constants.JSON_LIST].items():
            sidecar_dict = json.dumps(s_string)
            for key, item in sidecar_dict.items():
                merged_sidecar[key] = item
        sidecar_str = json.dumps(merged_sidecar)
    if sidecar_str:
        arguments[base_constants.JSON_SIDECAR] = Sidecar(file=io.StringIO(sidecar_str), name=f"JSON_Sidecar")
    else:
        arguments[base_constants.JSON_SIDECAR] = None


def get_input_objects(arguments, params):
    """ Update arguments with the information in the params dictionary.

    Args:
        arguments (dict):  A dictionary with the extracted parameters that are to be processed.
        params (dict): A dictionary of the service request values.

    Updates the arguments dictionary with the input objects including events, spreadsheets, schemas or strings.

    """

    if base_constants.EVENTS_STRING in params and params[base_constants.EVENTS_STRING]:
        arguments[base_constants.EVENTS] = \
            TabularInput(file=io.StringIO(params[base_constants.EVENTS_STRING]),
                         sidecar=arguments.get(base_constants.JSON_SIDECAR, None), name='Events')
    if base_constants.SPREADSHEET_STRING in params and params[base_constants.SPREADSHEET_STRING]:
        tag_columns, prefix_dict = spreadsheet.get_prefix_dict(params)
        has_column_names = arguments.get(base_constants.HAS_COLUMN_NAMES, None)
        arguments[base_constants.SPREADSHEET] = \
            SpreadsheetInput(file=io.StringIO(params[base_constants.SPREADSHEET_STRING]), file_type=".tsv",
                             tag_columns=tag_columns, has_column_names=has_column_names,
                             column_prefix_dictionary=prefix_dict, name='spreadsheet.tsv')
    if base_constants.STRING_LIST in params and params[base_constants.STRING_LIST]:
        s_list = []
        for s in params[base_constants.STRING_LIST]:
            s_list.append(HedString(s))
        arguments[base_constants.STRING_LIST] = s_list


def get_service_info(params):
    """ Get a dictionary with the service request command information filled in..

    Args:
        params (dict): A dictionary of the service request values.

    Returns:
        dict: A dictionary with the command, command target and options resolved from the service request.

    """
    service = params.get(base_constants.SERVICE, '')
    command = service
    command_target = ''
    pieces = service.split('_', 1)
    if command != "get_services" and len(pieces) == 2:
        command = pieces[1]
        command_target = pieces[0]
    has_column_names = params.get(base_constants.HAS_COLUMN_NAMES, '') == 'on'
    expand_defs = params.get(base_constants.EXPAND_DEFS, '') == 'on'
    check_for_warnings = params.get(base_constants.CHECK_FOR_WARNINGS, '') == 'on'
    include_description_tags = params.get(base_constants.INCLUDE_DESCRIPTION_TAGS, '') == 'on'

    return {base_constants.SERVICE: service,
            base_constants.COMMAND: command,
            base_constants.COMMAND_TARGET: command_target,
            base_constants.HAS_COLUMN_NAMES: has_column_names,
            base_constants.CHECK_FOR_WARNINGS: check_for_warnings,
            base_constants.EXPAND_DEFS: expand_defs,
            base_constants.INCLUDE_DESCRIPTION_TAGS: include_description_tags
            # base_constants.TAG_COLUMNS: tag_columns,
            # base_constants.COLUMN_PREFIX_DICTIONARY: prefix_dict
            }


def get_input_schema(parameters):
    """ Get a HedSchema or HedSchemaGroup object from the parameters.

    Args:
        parameters (dict): A dictionary of parameters extracted from the service request.

    """
    the_schema = None
    try:
        if base_constants.SCHEMA_STRING in parameters and parameters[base_constants.SCHEMA_STRING]:
            the_schema = hedschema.from_string(parameters[base_constants.SCHEMA_STRING])
        elif base_constants.SCHEMA_URL in parameters and parameters[base_constants.SCHEMA_URL]:
            schema_url = parameters[base_constants.SCHEMA_URL]
            the_schema = hedschema.load_schema(schema_url)
        elif base_constants.SCHEMA_VERSION in parameters and parameters[base_constants.SCHEMA_VERSION]:
            hed_file_path = hedschema.get_path_from_hed_version(parameters[base_constants.SCHEMA_VERSION])
            the_schema = hedschema.load_schema(hed_file_path)
    except HedFileError:
        the_schema = None

    return the_schema


def process(arguments):
    """ Call the desired service processing function and return the results in a standard format.

    Args:
        arguments (dict): A dictionary of arguments for the processing resolved from the request.

    Returns:
        dict: A dictionary of results in standard response format to be jsonified.

    """

    command = arguments.get(base_constants.COMMAND, '')
    target = arguments.get(base_constants.COMMAND_TARGET, '')
    response = {base_constants.SERVICE: arguments.get(base_constants.SERVICE, ''),
                'results': '', 'error_type': '', 'error_msg': ''}

    if not arguments.get(base_constants.SERVICE, ''):
        response["error_type"] = 'HEDServiceMissing'
        response["error_msg"] = "Must specify a valid service"
    elif command == 'get_services':
        response["results"] = services_list()
    elif target == "events":
        response["results"] = events.process(arguments)
    elif target == "sidecar":
        response["results"] = sidecar.process(arguments)
    elif target == "spreadsheet":
        results = spreadsheet.process(arguments)
        response["results"] = package_spreadsheet(results)
    elif target == "strings":
        response["results"] = strings.process(arguments)
    else:
        response["error_type"] = 'HEDServiceNotSupported'
        response["error_msg"] = f"{command} for {target} not supported"
    return response


def package_spreadsheet(results):
    """ Get the transformed results dictionary where spreadsheets are converted to strings.

    Args:
        results (dict): The dictionary of results in standardized form returned from processing.

    Returns:
        dict: The results transformed so that all entries are strings.


    """
    if results['msg_category'] == 'success' and base_constants.SPREADSHEET in results:
        results[base_constants.SPREADSHEET] = results[base_constants.SPREADSHEET].to_csv(file=None)
    elif base_constants.SPREADSHEET in results:
        del results[base_constants.SPREADSHEET]
    return results


def services_list():
    """ Get a formatted string describing services using the resources/services.json file

     Returns:
        str: A formatted string listing available services.

     """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    the_path = os.path.join(dir_path, 'static/resources/services.json')
    with open(the_path) as f:
        service_info = json.load(f)
    services = service_info['services']
    meanings = service_info['parameter_meanings']
    returns = service_info['returns']
    results = service_info['results']
    services_string = '\nServices:\n'
    for service, info in services.items():
        description = info['Description']
        parameters = get_parameter_string(info['Parameters'])

        return_string = info['Returns']
        next_string = \
            f'\n{service}:\n\tDescription: {description}\n{parameters}\n\tReturns: {return_string}\n'
        services_string += next_string

    meanings_string = '\nParameter meanings:\n'
    for string, meaning in meanings.items():
        meanings_string += f'\t{string}: {meaning}\n'

    returns_string = '\nReturn values:\n'
    for return_val, meaning in returns.items():
        returns_string += f'\t{return_val}: {meaning}\n'

    results_string = '\nResults field meanings:\n'
    for result_val, meaning in results.items():
        results_string += f'\t{result_val}: {meaning}\n'
    data = services_string + meanings_string + returns_string + results_string
    return {base_constants.COMMAND: 'get_services', base_constants.COMMAND_TARGET: '',
            'data': data, 'output_display_name': '',
            base_constants.SCHEMA_VERSION: '', 'msg_category': 'success',
            'msg': "List of available services and their meanings"}


def get_parameter_string(params):
    if not params:
        return "\tParameters: []"
    param_list = []
    for p in params:
        if isinstance(p, list):
            param_list.append(" or ".join(p))
        else:
            param_list.append(p)

    return "\tParameters:\n\t\t" + "\n\t\t".join(param_list)
