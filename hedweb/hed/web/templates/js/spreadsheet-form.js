const EXCEL_FILE_EXTENSIONS = ['xlsx', 'xls'];
const TEXT_FILE_EXTENSIONS = ['tsv', 'txt'];
const VALID_FILE_EXTENSIONS = ['xlsx', 'xls', 'tsv', 'txt']
$(function () {
    prepareForm();
});

/**
 * Spreadsheet event handler function. Checks if the file uploaded has a valid spreadsheet extension.
 */
$('#spreadsheet-file').on('change', function () {
    let spreadsheet = $('#spreadsheet-file');
    let spreadsheetPath = spreadsheet.val();
    let spreadsheetFile = spreadsheet[0].files[0];
    clearSpreadsheetFlashMessages();

    if (!fileHasValidExtension(spreadsheetPath, VALID_FILE_EXTENSIONS)) {
        clearForm();
        flashMessageOnScreen('Upload a valid spreadsheet (.xlsx, .xls, .tsv, .txt)', 'error', 'spreadsheet-flash');
        return
    }
    clearTagColumnTextboxes();
    updateFileLabel(spreadsheetPath, '#spreadsheet-display-name');
    if (fileHasValidExtension(spreadsheetPath, EXCEL_FILE_EXTENSIONS)) {
        getWorksheetsInfo(spreadsheetFile);
        showWorksheetSelect();
    }
    else if (fileHasValidExtension(spreadsheetPath, TEXT_FILE_EXTENSIONS)) {
        $('#worksheet-name').empty();
        getWorksheetsInfo(spreadsheetFile);
        hideWorksheetSelect();
    }
});

/**
 * Submits the form if the tag columns textbox is valid.
 */
$('#spreadsheet-validation-submit').on('click', function () {
    if (fileIsSpecified('#spreadsheet-file', 'spreadsheet-flash', 'Spreadsheet is not specified.') &&
        tagColumnsTextboxIsValid() && hedSpecifiedWhenOtherIsSelected()) {
        submitForm();
    }
});

/**
 * Gets the information associated with the Excel worksheet that was newly selected. This information contains
 * the names of the columns and column indices that contain HED tags.
 */
$('#worksheet-name').on('change', function () {
    let spreadsheetFile = $('#spreadsheet-file')[0].files[0];
    let worksheetName = $('#worksheet-name option:selected').text();
    // $('#worksheet-name').val(worksheetName)
    clearSpreadsheetFlashMessages();
    getWorksheetsInfo(spreadsheetFile, worksheetName, false);
});

/**
 * Clear the fields in the form.
 */
function clearForm() {
    $('#spreadsheet-form')[0].reset();
    $('#spreadsheet-display-name').text('');
    $('#worksheet-name').empty();
    clearTagColumnTextboxes();
    hideColumnNames();
    hideWorksheetSelect()
    hideOtherHEDVersionFileUpload()
}

/**
 * Clear the flash messages that aren't related to the form submission.
 */
function clearSpreadsheetFlashMessages() {
    flashMessageOnScreen('', 'success', 'spreadsheet-flash');
    flashMessageOnScreen('', 'success', 'tag-columns-flash');
    flashMessageOnScreen('', 'success', 'hed-select-flash');
    flashMessageOnScreen('', 'success', 'spreadsheet-validation-submit-flash');
}

/**
 * Gets information associated with the Excel workbook worksheets. This information contains the names of the
 * worksheets, the names of the columns in the first worksheet, and column indices that contain HED tags in the
 * first worksheet.
 * @param {Object} workbookFile - An Excel workbook file.
 * @param {string} worksheetName - name of worksheet or undefined.
 * @param {boolean} repopulate - if true repopulate the select pull down with worksheet names
 */
function getWorksheetsInfo(workbookFile, worksheetName=undefined, repopulate=true) {
    let formData = new FormData();
    formData.append('columns-file', workbookFile);
    if (worksheetName !== undefined) {
        formData.append('worksheet-selected', worksheetName)
    }
    $.ajax({
        type: 'POST',
        url: "{{url_for('route_blueprint.get_columns_info_results')}}",
        data: formData,
        contentType: false,
        processData: false,
        dataType: 'json',
        success: function (worksheetsInfo) {
            if (repopulate) {
                populateWorksheetDropdown(worksheetsInfo['worksheet-names']);
            }
            setComponentsRelatedToColumns(worksheetsInfo, true);
        },
        error: function (jqXHR) {
            flashMessageOnScreen('Spreadsheet could not be processed.', 'error',
                'spreadsheet-flash');
        }
    });
}


/**
 * Hides  worksheet select section in the form.
 */
function hideWorksheetSelect() {
    $('#worksheet-select').hide();
}

/**
 * Populate the Excel worksheet select box.
 * @param {Array} worksheetNames - An array containing the Excel worksheet names.
 */
function populateWorksheetDropdown(worksheetNames) {
    if (Array.isArray(worksheetNames) && worksheetNames.length > 0) {
        let worksheetDropdown = $('#worksheet-name');
        showWorksheetSelect();
        worksheetDropdown.empty();
        for (let i = 0; i < worksheetNames.length; i++) {
            $('#worksheet-name').append(new Option(worksheetNames[i], worksheetNames[i]) );
        }
    }
}

/**
 * Prepare the validation form after the page is ready. The form will be reset to handle page refresh and
 * components will be hidden and populated.
 */
function prepareForm() {
    clearForm();
    getHEDVersions()
    hideColumnNames();
    hideWorksheetSelect();
    hideOtherHEDVersionFileUpload();
}


/**
 * Show the worksheet select section.
 */
function showWorksheetSelect() {
    $('#worksheet-select').show();
}


/**
 * Submit the form and return the validation results. If there are issues then they are returned in an attachment
 * file.
 */
function submitForm() {
    let spreadsheetForm = document.getElementById("spreadsheet-form");
    let formData = new FormData(spreadsheetForm);
    let worksheetName = $('#worksheet-select option:selected').text();
    formData.append('worksheet-selected', worksheetName)
    let prefix = 'issues';
    if(worksheetName) {
        prefix = prefix + '_worksheet_' + worksheetName;
    }
    let spreadsheetFile = $('#spreadsheet-file')[0].files[0].name;
    let display_name = convertToResultsName(spreadsheetFile, prefix)
    clearSpreadsheetFlashMessages();
    flashMessageOnScreen('Worksheet is being validated ...', 'success',
        'spreadsheet-validation-submit-flash')
    $.ajax({
            type: 'POST',
            url: "{{url_for('route_blueprint.get_spreadsheet_validation_results')}}",
            data: formData,
            contentType: false,
            processData: false,
            dataType: 'text',
            success: function (download, status, xhr) {
                getResponseSuccess(download, xhr, display_name, 'spreadsheet-validation-submit-flash')
            },
            error: function (download, status, xhr) {
                getResponseFailure(download, xhr, display_name, 'spreadsheet-validation-submit-flash')
            }
        }
    )
}
