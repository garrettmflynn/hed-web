from os.path import basename
from urllib.parse import urlparse
from flask import current_app
from werkzeug.utils import secure_filename

from hed import schema as hedschema
from hed.util import get_file_extension
from hed.errors import get_exception_issue_string, get_printable_issue_string
from hed.errors import HedFileError
from hed.util import generate_filename
from web_util import form_has_file, form_has_option, form_has_url
from constants import base_constants, file_constants

app_config = current_app.config


def get_schema(arguments):
    """ Return a HedSchema object from the given parameters.

    Args:
        arguments (dict): A dictionary with the input arguments extracted from the schema form or service request.

    Returns:
        HedSchema: The extracted HedSchema object if successful
        list: A list of issues if problems or an empty list if successful.
    """
    hed_schema = None
    issues = []
    file_found = True
    try:
        if base_constants.SCHEMA_FILE in arguments:
            hed_schema = hedschema.load_schema(arguments[base_constants.SCHEMA_FILE])
        elif base_constants.SCHEMA_URL in arguments:
            hed_schema = hedschema.load_schema(arguments[base_constants.SCHEMA_URL])
        elif base_constants.SCHEMA_STRING in arguments:
            hed_schema = hedschema.from_string(arguments[base_constants.SCHEMA_STRING],
                                               file_type=arguments[base_constants.SCHEMA_FILE_TYPE])
        else:
            file_found = False
    except HedFileError as e:
        issues = e.issues
    if not file_found:
        raise HedFileError("NoSchemaProvided", "Must provide a loadable schema", "")
    return hed_schema, issues


def get_input_from_form(request):
    """ Extract a dictionary of input for processing from the schema form.

    Args:
        request (Request): A Request object containing user data from the schema form.

    Returns:
        dict: A dictionary of schema processing parameters in standard form.

    Raises:
        HedFileError:  If the input arguments were missing or not valid.

    """

    arguments = { base_constants.COMMAND: request.form.get(base_constants.COMMAND_OPTION, ''),
                  base_constants.CHECK_FOR_WARNINGS:
                  form_has_option(request, base_constants.CHECK_FOR_WARNINGS, 'on')
                }
    if form_has_option(request, base_constants.SCHEMA_UPLOAD_OPTIONS, base_constants.SCHEMA_FILE_OPTION) and \
            form_has_file(request, base_constants.SCHEMA_FILE, file_constants.SCHEMA_EXTENSIONS):
        f = request.files[base_constants.SCHEMA_FILE]
        arguments[base_constants.SCHEMA_STRING] = f.read(file_constants.BYTE_LIMIT).decode('ascii')
        arguments[base_constants.SCHEMA_FILE_TYPE] = secure_filename(f.filename)
        arguments[base_constants.SCHEMA_DISPLAY_NAME] = secure_filename(f.filename)
    elif form_has_option(request, base_constants.SCHEMA_UPLOAD_OPTIONS, base_constants.SCHEMA_URL_OPTION) and \
            form_has_url(request, base_constants.SCHEMA_URL, file_constants.SCHEMA_EXTENSIONS):
        arguments[base_constants.SCHEMA_URL] = request.values[base_constants.SCHEMA_URL]
        url_parsed = urlparse(arguments[base_constants.SCHEMA_URL])
        arguments[base_constants.SCHEMA_FILE_TYPE] = basename(url_parsed.path)
        arguments[base_constants.SCHEMA_DISPLAY_NAME] = basename(url_parsed.path)
    else:
        raise HedFileError("NoSchemaProvided", "Must provide a loadable schema", "")
    return arguments


def process(arguments):
    """ Perform the requested action for the schema.

    Args:
        arguments (dict): A dictionary with the input arguments extracted from the schema form or service request.

    Returns:
        dict: A dictionary of results in the standard results format.

    Raises:
        HedFileError:  If the command was not found or the input arguments were not valid.

    """
    display_name = arguments.get('schema_display_name', 'unknown_source')
    hed_schema, issues = get_schema(arguments)
    if issues:
        issue_str = get_exception_issue_string(issues, f"Schema for {display_name} had these errors")
        file_name = generate_filename(arguments[base_constants.SCHEMA_DISPLAY_NAME],
                                      name_suffix='schema__errors', extension='.txt')
        return {'command': arguments[base_constants.COMMAND],
                base_constants.COMMAND_TARGET: 'schema',
                'data': issue_str, 'output_display_name': file_name,
                'schema_version': 'unknown', 'msg_category': 'warning',
                'msg': f'Schema {display_name} invalid and could not be loaded'}

    if base_constants.COMMAND not in arguments or arguments[base_constants.COMMAND] == '':
        raise HedFileError('MissingCommand', 'Command is missing', '')
    elif arguments[base_constants.COMMAND] == base_constants.COMMAND_VALIDATE:
        results = schema_validate(hed_schema, display_name)
    elif arguments[base_constants.COMMAND] == base_constants.COMMAND_CONVERT_SCHEMA:
        results = schema_convert(hed_schema, display_name)
    else:
        raise HedFileError('UnknownProcessingMethod', "Select a schema processing method", "")
    return results


def schema_convert(hed_schema, display_name):
    """ Return a string representation of hed_schema in the desired format as determined by the display name extention.

    Args:
        hed_schema (HedSchema): A HedSchema object containing the schema to be processed.
        display_name (str): The schema display name whose extension determines the conversion format.

    Returns:
        dict: A dictionary of results in the standard results format.

    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown')
    schema_format = get_file_extension(display_name)
    if schema_format == file_constants.SCHEMA_XML_EXTENSION:
        data = hed_schema.get_as_mediawiki_string()
        extension = '.mediawiki'
    else:
        data = hed_schema.get_as_xml_string()
        extension = '.xml'
    file_name = generate_filename(display_name,  extension=extension)

    return {'command': base_constants.COMMAND_CONVERT_SCHEMA,
            base_constants.COMMAND_TARGET: 'schema',
            'data': data, 'output_display_name': file_name,
            'schema_version': schema_version, 'msg_category': 'success',
            'msg': 'Schema was successfully converted'}


def schema_validate(hed_schema, display_name):
    """ Run schema compliance for HED-3G.

    Args:
        hed_schema (HedSchema): A HedSchema object containing the schema to be processed.
        display_name (str): The display name associated with this schema object (used in error reports).

    Returns:
        dict: A dictionary of results in the standard results format.

    """

    schema_version = hed_schema.header_attributes.get('version', 'Unknown')
    issues = hed_schema.check_compliance()
    if issues:
        issue_str = get_printable_issue_string(issues, f"Schema HED 3G compliance errors for {display_name}:")
        file_name = generate_filename(display_name, name_suffix='schema_3G_compliance_errors', extension='.txt')
        return {'command': base_constants.COMMAND_VALIDATE,
                base_constants.COMMAND_TARGET: 'schema',
                'data': issue_str, 'output_display_name': file_name,
                'schema_version': schema_version, 'msg_category': 'warning',
                'msg': 'Schema is not HED 3G compliant'}
    else:
        return {'command': base_constants.COMMAND_VALIDATE,
                base_constants.COMMAND_TARGET: 'schema',
                'data': '', 'output_display_name': display_name,
                'schema_version': schema_version, 'msg_category': 'success',
                'msg': 'Schema had no HED-3G validation errors'}
