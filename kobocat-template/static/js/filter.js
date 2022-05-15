//# this File is to populate various filter



/***
 * Dropdown ELEMENT CREATE
 * @param element  --New created element id field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param jsondata  --json having id and name
 *
 * @author persia
 */
function dropdownControlCreate(element, parent_div_id, control_name, control_label, has_cascaded_element, jsondata, appearance, username) {
    var col_md = 12;
    if ('col_md' in appearance)
        col_md = appearance['col_md'];
    var wrapper_class = ""
    if ('wrapper_class' in appearance)
        wrapper_class = appearance['wrapper_class'];

    //Default value select
    var select_default = '#none';
    if ('select_default' in appearance)
        select_default = appearance['select_default'];


    //Select 1st option
    var select_initial = false;
    if ('select_initial' in appearance)
        select_initial = appearance['select_initial'];
    if (select_initial == true) select_initial = 'selected';
    var multiple = '';
    if ('multiple_select' in appearance && appearance['multiple_select']){
        multiple='multiple' ;
    }

    var start_wrapper = '<div class ="col-md-3' + wrapper_class + ' " >';
    var end_wrapper = '</div>';
    var label = '<label>' + control_label + '</label>';
    var dropdown_html = start_wrapper + label + '</div><div class ="col-md-6 col-md-offset-3"><select style="width:100%" id="' + element + '" name="' + control_name + '" class="form-control" onchange="' + has_cascaded_element + '" '+multiple+'> <option value="">Select</option>';

    if (jsondata) {
        for (var i = 0; i < jsondata.length; i++) {
            if (jsondata[i].id == select_default) select_initial = 'selected';
            dropdown_html += '<option ' + select_initial + '    value="' + jsondata[i]['value'] + '">' + jsondata[i]['name'] + '</option>';
            select_initial = '';
        }
    }
    dropdown_html += '</select>' + end_wrapper;
    $("#" + parent_div_id).html(dropdown_html);
    handleSelectPicker(element);
} //END of checkboxControlCreate


function getOptionDropdown(jsondata,element){
    dropdown_html = ''
	for (key in jsondata) {
            dropdown_html += '<option     value="' + key + '">' + jsondata[key] + '</option>';
	}
    dropdown_html+='</select>';
    return dropdown_html;
}

/***
 * text Filter (Submit Type) CREATE
 * @param element  --New created element id field
 * @param parent_div_id  -- parent div of new elements
 * @param control_label -- visible label
 *
 * @author persia
 */
function textControlCreate(element, parent_div_id, control_name, control_label,options,type) {
    var start_wrapper = '<div>';
    var end_wrapper = '</div>';
    var label = '<div class="col-md-3" ><label>'+control_label+'</label></div>';
    var condition_html = '';
    if (options) {
        condition_html = getOptionDropdown(options,element)
        condition_html = '<div class="col-md-3"><select name="'+control_name+'_condition" class="form-control"><option value=""> Select </option>'+condition_html+'</select></div>'
    }
    var input_html = '';
    var button_html = start_wrapper +label+ condition_html+ '<div class="col-md-6"><input name="'+control_name+'_input1" id="' + element + '" type="'+type+'" class="form-control"       ></div>'+ end_wrapper;
    $("#" + parent_div_id).append(button_html);
} //END of textControlCreate

/***
 * Button (Submit Type) CREATE
 * @param element  --New created element id field
 * @param parent_div_id  -- parent div of new elements
 * @param control_label -- visible label
 *
 * @author persia
 */
function buttonControlCreate(element, parent_div_id, control_label) {
    var start_wrapper = '<div class="mp_submit" ><div class ="col-md-2" >  ';
    var end_wrapper = '</div></div>';
    var button_html = start_wrapper + '<input id="' + element + '" type="submit" class="btn btn-primary"  value="' + control_label + '"     >' + end_wrapper;
    $("#" + parent_div_id).append(button_html);
} //END of checkboxControlCreate


/***
 * Multiple Select ELEMENT CREATE
 * @param element  --New created element id field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param jsondata  --json having id and name
 *
 * @author persia
 */
function multipleSelectControlCreate(element, parent_div_id, control_name, control_label, has_cascaded_element, jsondata, appearance, username) {
    if (jsondata == null) {
        console.log(control_label + " element cannot be created -mpower");
        return;
    }
    var col_md = 12;
    if ('col_md' in appearance)
        col_md = appearance['col_md'];
    var wrapper_class = ""
    if ('wrapper_class' in appearance)
        wrapper_class = appearance['wrapper_class'];
    var start_wrapper = '<div class ="  "> <div class ="col-md-' + col_md + ' ' + wrapper_class + '" >';
    var end_wrapper = '</div></div>';
    var label = '<label class="control-label">' + control_label + '</label> <div  >';
    var multiple_select_html = start_wrapper + label + '<select multiple="multiple"   onchange="' + has_cascaded_element + '" id="' + element + '" name="' + control_name + '" class="form-control">';
    for (var i = 0; i < jsondata.length; i++) {
        multiple_select_html += '<option value="' + jsondata[i].id + '">' + jsondata[i].name + '</option>';
    }
    multiple_select_html += '</select></div>' + end_wrapper;
    $("#" + parent_div_id).append(multiple_select_html);
    console.log("here In multiselect " + element);
    handleMultipleSelect(element);
} //END of multipleSelectControlCreate


/***
 * CHECKBOX ELEMENT CREATE
 * @param element  --New created element class field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param jsondata  --json having id and name
 *
 * @author persia
 */
function checkboxControlCreate(element, parent_div_id, control_name, control_label, jsondata) {
    var start_wrapper = '<div class ="controls  "> <div class ="form-group" >';
    var end_wrapper = '</div></div>';
    var label = '<label>' + control_label + '</label>';
    var checkbox_html = start_wrapper + label + '<div class="checkbox-list">';
    for (var i = 0; i < jsondata.length; i++) {
        checkbox_html += '<label><input class="' + element + '" type="checkbox" name="' + control_name + '" value="' + jsondata[i].id + '">' + jsondata[i].name + '</label>';
    }
    checkbox_html += '</div>' + end_wrapper;
    $("#" + parent_div_id).append(checkbox_html);
} //END of checkboxControlCreate


/***
 * Radio button ELEMENT CREATE
 * @param element  --New created element class field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param jsondata  --json having id and name
 *
 * @author persia
 */
function radioControlCreate(element, parent_div_id, control_name, control_label, jsondata) {
    var start_wrapper = '<div class ="controls  "> <div class ="form-group" >';
    var end_wrapper = '</div></div>';
    var label = '<label>' + control_label + '</label>';
    var radio_html = start_wrapper + label + '<div class="checkbox-list">';
    for (var i = 0; i < jsondata.length; i++) {
        radio_html += '<label><input class="' + element + '" type="radio" name="' + control_name + '" value="' + jsondata[i].id + '">' + jsondata[i].name + '</label>';
    }
    radio_html += '</div>' + end_wrapper;
    $("#" + parent_div_id).append(radio_html);
} //END of radioControlCreate


/***
 * range slider  ELEMENT CREATE
 * @param element  --New created element class field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param appearance  --json having initial value, range
 *
 * @author zinia
 */
function sliderControlCreate(element, parent_div_id, control_name, control_label, appearance) {
    var col_md = 12;
    var initial = 100;
    var range = "min";
    if ('col_md' in appearance)
        col_md = appearance['col_md'];
    if ('initial' in appearance)
        initial = appearance['initial'];
    if ('range' in appearance)
        range = appearance['range'];

    var start_wrapper = '<div class ="col-md-' + col_md + ' controls " > <div class ="form-group" >';
    var end_wrapper = '</div></div>';
    var label = '<label>' + control_label + '</label>';
    var slider_html = start_wrapper + '<p> ' + label + ': <input type = "text" id = "no_' + element + '"style = "border:0; color:#b9cd6d; font-weight:bold;"  > <input type="hidden" id="' + element + '" value = "" class="form_control" name="' + control_name + '"></p>';
    slider_html += '<div id = "slider_' + element + '"></div>' + end_wrapper;
    $("#" + parent_div_id).append(slider_html);
    handleSlider(element, initial, range);
}

/***
 * Date Field CREATE
 * @param element  --New created element class field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param initialdate  --initial date
 *
 * @author zinia
 */
function dateControlCreate(element, parent_div_id, control_name, control_label,  appearance_json) {
    var start_wrapper = '<div class ="col-md-3"> ';
    var end_wrapper = '</div></div>';
    var label = '<label>' + control_label + '</label></div>';
    var date_input_html = start_wrapper + label + '<div class="col-md-6 col-md-offset-3" >';
    date_input_html += '<input type="text" id="' + element + '" name="'+control_name+'" class="form-control"/></div> ';
    $("#" + parent_div_id).append(date_input_html);

    handleDateRangePicker(appearance_json,element);

} //END of radioControlCreate


var handleDateRangePicker= function(appearance_json,element){
	$('#'+element).daterangepicker();
}

/***
 * TEXT Input Field CREATE
 * @param element  --New created element class field
 * @param parent_div_id  -- parent div of new elements
 * @param control_name   -- name field of control
 * @param control_label -- visible label
 * @param initialvalue  --initial value
 *
 * @author persia
 */
function textinputControlCreate(element, parent_div_id, control_name, control_label, initialvalue) {
    var start_wrapper = '<div class ="controls  "> <div class ="form-group" > ';
    var end_wrapper = '</div></div>';
    var label = '<label>' + control_label + '</label>';
    var text_input_html = start_wrapper + label;
    text_input_html += '<input type="text" id="' + element + '" name="' + control_name + '" class="form-control" value="' + initialvalue + '" /> ' + end_wrapper;
    $("#" + parent_div_id).append(text_input_html);
    //handleDatePickers();
} //END of textinputControlCreate


/**
 * Bootstrap Datepicker Function
 * @param element
 *
 * @author zinia
 */
var handleDatePickers = function (appearance_json) {
    // rtl: App.isRTL(),
    appearance_json["autoclose"] = true;
    console.log(appearance_json);
    $('.datepicker').datepicker(appearance_json);
    if (jQuery().datepicker) {
        $('.datepicker').datepicker(appearance_json);
        $('body').removeClass("modal-open"); // fix bug when inline picker is used in modal
    }


} // End of handleDatePickers


var handleSelectPicker = function(element){
    $('#'+element).selectpicker();

}

/**
 * Bootstrap Multiple Select Function
 * @param element
 *
 * @persia
 */
var handleMultipleSelect = function (element) {
    console.log("everything");
    console.log('All selected');
    $("#" + element).multiselect({
        enableFiltering: true,
        //filterBehavior: 'value',
        maxHeight: 200,
        numberDisplayed: 1,
        includeSelectAllOption: true,
        buttonWidth: '100%',
        allSelectedText: 'All Selected'
    });
}

/**
 * Bootstrap slider function
 * @param element
 * @param initial value
 * @param range
 * @author zinia
 */
var handleSlider = function (element, initial, range) {

    $("#no_" + element).val(" 0 - " + initial);
    $("#" + element).val("" + initial);
    $("#slider_" + element).slider({
        range: "min",
        min: 0,
        max: 200,
        value: initial,
        change: function (event, ui) {
            console.log(ui.value);
            $("#no_" + element).val(" 0 - " + ui.value);
            $("#" + element).val("" + ui.value);
            //console.log(ui.values[0]); console.log(ui.values[1]);

        }
    });
}