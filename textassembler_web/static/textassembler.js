/*
Javascript to control the optional filters on the page
*/

function updateElementIndex(el, prefix, ndx) {
    var id_regex = new RegExp('(' + prefix + '-\\d+)');
    var replacement = prefix + '-' + ndx;
    if ($(el).attr("for")) $(el).attr("for", $(el).attr("for").replace(id_regex, replacement));
    if (el.id) el.id = el.id.replace(id_regex, replacement);
    if (el.name) el.name = el.name.replace(id_regex, replacement);
}
function cloneMore(selector, prefix) {
    var newElement = $(selector).clone(true);
    var total = $('#id_' + prefix + '-TOTAL_FORMS')[0].value;
    newElement.find(':input').each(function() {
        if (typeof($(this).attr('name')) == 'undefined') return;
        var name = $(this).attr('name').replace('-' + (total-1) + '-', '-' + total + '-');
        var id = 'id_' + name;
        $(this).attr({'name': name, 'id': id}).val('').removeAttr('checked');
    });
    total++;
    $('#id_' + prefix + '-TOTAL_FORMS')[0].value =total;
    $(selector).after(newElement);
    var conditionRow = $('.form-row:not(:last)');
    conditionRow.find('.btn.add-form-row')
    .removeClass('btn-success').addClass('btn-danger')
    .removeClass('add-form-row').addClass('remove-form-row')
    .html('-');
    return false;
}
function deleteForm(prefix, btn) {
    var total = parseInt($('#id_' + prefix + '-TOTAL_FORMS')[0].value);
    if (total > 0){
        btn.closest('.form-row').remove();
        var forms = $('.search_filters');
        $('#id_' + prefix + '-TOTAL_FORMS')[0].value = forms.length;
        for (var i=0, formCount=forms.length; i<formCount; i++) {
            $(forms.get(i)).find(':input').each(function() {
                updateElementIndex(this, prefix, i);
            });
        }
    }
    return false;
}

function addFilterRow(data, selected_filter, selected_filter_value='') {
    var newRow =
        "<div class='row form-row spacer'>" +
        "<div class='col-4 filter_type_label'><label>&bull; " + data['name'];

    if (data['help'] != ''){
        // Allow tables to be in popover content
        $.fn.popover.Constructor.Default.whiteList.table = [];
        $.fn.popover.Constructor.Default.whiteList.tr = [];
        $.fn.popover.Constructor.Default.whiteList.td = [];
        $.fn.popover.Constructor.Default.whiteList.div = [];
        $.fn.popover.Constructor.Default.whiteList.tbody = [];
        $.fn.popover.Constructor.Default.whiteList.thead = [];
        newRow += "&nbsp;<a href='' role='button' onClick='return false;' data-trigger='focus' data-html='true' data-toggle='popover' title='" + data['name'] +
            "' data-content='" + data['help'] + "'>(?)</a>"
    }

    newRow += "</label></div>" +
            "<div class='col-6'>" +
                "<div class='input-group'>" +
                    "<div class='filter_opt_value'>";

    switch(data["type"]){
        case "text":
            newRow += "<input type='text' name='" + selected_filter + "' class='form-control' ";
            if (selected_filter_value && selected_filter_value.length == 1){
                newRow += "value='" + selected_filter_value[0] + "'";
            }
            newRow += "></input>";
            break;
        case "select":
            newRow += "<select name='" + selected_filter + "' class='sp' multiple data-live-search='true' data-width='100%'>";
            var i = 0;
            for (i=0; i< data["choices"].length; i++){
                newRow += "<option value='" + data["choices"][i]['val'] + "'";
                for (filter in selected_filter_value) {
                    if (selected_filter_value[filter] == data["choices"][i]['val']) {
                        newRow += " selected";
                    }
                }
                newRow += ">" + data["choices"][i]['name'] + "</option>";
            }
            newRow += "</select>";
            break;
        case "date":
            newRow += "<select name='" + selected_filter + "' class='sp comp-dd' data-width='15%'>";
            var i = 0;
            for (i=0; i< data["choices"].length; i++){
                newRow += "<option value='" + data["choices"][i]['val'] + "'";
                if (selected_filter_value != null && selected_filter_value.length == 2){
                    if (selected_filter_value[0] == data["choices"][i]['val']){
                        newRow += " selected";
                    }
                }
                newRow += ">" + data["choices"][i]['name'] + "</option>";
            }
            newRow += "</select><input type ='date' name='" + selected_filter + "' class='form-control filter-date'";
            if (selected_filter_value != null && selected_filter_value.length == 2){
                newRow += " value='" + selected_filter_value[1] + "'";
            }
            newRow += "/>";
            break;
    }

    newRow += "</div>" +
              "</div>" +
              "</div>" +
            "<div class='input-group-append'>" +
                "<button class='btn btn-danger remove-form-row'>-</button>" +
            "</div></div>";
    $(".search_filters").append(newRow);
    $(".sp").selectpicker();
    $('[data-toggle="popover"]').popover();
    $("#id_filter_opts").val("");

}
function displayFilterValues(selected_filter, selected_filter_value='') {
    $.ajax({
        url: '/ajax/filter_val_input/'+selected_filter,
        dataType: 'json',
        success: function(data) {
            if (selected_filter_value === '' || selected_filter_value === null){
                addFilterRow(data, selected_filter, selected_filter_value);
            }
            else {
                switch(data["type"]){
                    case "text":
                        for (filter_value in selected_filter_value){
                            addFilterRow(data, selected_filter, [selected_filter_value[filter_value]]);
                        }
                        break;
                    case "select":
                        addFilterRow(data, selected_filter, selected_filter_value);
                        break;
                    case "date":
                        for (i=0; i< selected_filter_value.length; i=i+2) {
                            addFilterRow(data, selected_filter, selected_filter_value.slice(i,i+2));
                        }
                        break;
                }
            }
        }
    });
}
$(document).on('click', '.add-form-row', function(e){
    e.preventDefault();
    cloneMore('.form-row:last', 'form');
    return false;
});
$(document).on('click', '.remove-form-row', function(e){
    e.preventDefault();
    deleteForm('form', $(this));
    return false;
});

$(document).on('change', '#id_filter_opts', function(e) {
    var selected_filter = this.value;
    var selected_filter_name = this.options[this.selectedIndex].text;
    displayFilterValues(selected_filter, null);

});

/* 
Handle POST data to pre-populate the filters
*/
$( document ).ready(function() {
    post_data = $("#post_data")[0].value;
    if (post_data) {
        post_data = JSON.parse(post_data);
        for (filter in post_data) {
            values = post_data[filter];
            displayFilterValues(filter,values);
        }
    }
    $(".sp").selectpicker();
    $('[data-toggle="popover"]').popover();
});
