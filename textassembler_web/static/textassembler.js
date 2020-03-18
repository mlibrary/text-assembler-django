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
    newElement.find(':input').each(function () {
        if (typeof ($(this).attr('name')) == 'undefined') return;
        var name = $(this).attr('name').replace('-' + (total - 1) + '-', '-' + total + '-');
        var id = 'id_' + name;
        $(this).attr({'name': name, 'id': id}).val('').removeAttr('checked');
    });
    total++;
    $('#id_' + prefix + '-TOTAL_FORMS')[0].value = total;
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
    if (total > 0) {
        btn.closest('.form-row').remove();
        var forms = $('.search_filters');
        $('#id_' + prefix + '-TOTAL_FORMS')[0].value = forms.length;
        for (var i = 0, formCount = forms.length; i < formCount; i++) {
            $(forms.get(i)).find(':input').each(function () {
                updateElementIndex(this, prefix, i);
            });
        }
    }
    return false;
}

function addFilterRow(data, selected_filter, selected_filter_value = '') {
    var newRowClass = data['name'];
    var thisClassCount = $("." + newRowClass).length;
    var newRowID = newRowClass + thisClassCount;
    var newRow =
        "<div class='row form-row spacer'>" +
        "<div class='col-4 filter_type_label'><label class='" + newRowClass + "' for='" + newRowID + "'>&bull; " + data['name'];

    if (data['help'] && data['help'] != '') {
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

    switch (data["type"]) {
        case "text":
            newRow += "<input type='text' name='" + selected_filter + "' class='form-control' aria-label='" + selected_filter + "' ";
            if (selected_filter_value && selected_filter_value.length == 1) {
                newRow += "value='" + selected_filter_value[0] + "'";
            }
            newRow += "id='" + newRowID + "'></input>";
            break;
        case "select":
            newRow += "<select name='" + selected_filter + "' class='sp'  multiple data-live-search='true' data-width='100%' aria-label='" + selected_filter + "' id='" + newRowID + "'>";
            var i = 0;
            for (i = 0; i < data["choices"].length; i++) {
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
            newRow += "<select name='" + selected_filter + "' class='sp comp-dd' data-width='75%' aria-label='" + selected_filter + "' id='" + newRowID + "'>";
            var i = 0;
            for (i = 0; i < data["choices"].length; i++) {
                newRow += "<option value='" + data["choices"][i]['val'] + "'";
                if (selected_filter_value != null && selected_filter_value.length == 2) {
                    if (selected_filter_value[0] == data["choices"][i]['val']) {
                        newRow += " selected";
                    }
                }
                newRow += ">" + data["choices"][i]['name'] + "</option>";
            }
            newRow += "</select><input type ='date' name='" + selected_filter + "' class='form-control filter-date' aria-label='" + selected_filter + "' ";
            if (selected_filter_value != null && selected_filter_value.length == 2) {
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

function displayFilterValues(selected_filter, selected_filter_value = '') {
    $.ajax({
        url: '/ajax/filter_val_input/' + selected_filter,
        dataType: 'json',
        success: function (data) {
            if (selected_filter_value === '' || selected_filter_value === null) {
                addFilterRow(data, selected_filter, selected_filter_value);
            } else {
                switch (data["type"]) {
                    case "text":
                        for (filter_value in selected_filter_value) {
                            addFilterRow(data, selected_filter, [selected_filter_value[filter_value]]);
                        }
                        break;
                    case "select":
                        addFilterRow(data, selected_filter, selected_filter_value);
                        break;
                    case "date":
                        for (i = 0; i < selected_filter_value.length; i = i + 2) {
                            addFilterRow(data, selected_filter, selected_filter_value.slice(i, i + 2));
                        }
                        break;
                }
            }
        }
    });
}

function handleCheckChange(table) {

    //build a regex filter string with an or(|) condition
    var types = $('input:checkbox[name="filter"]:checked').map(function () {
        return '^' + this.value + '\$';
    }).get().join('|');

    //filter in column 0, with an regex, no smart filtering, no inputbox,not case sensitive
    table.fnFilter(types, 0, true, false, false, false);

    return;

    if ($("#hide_deleted").is(':checked')) {
        var hide_deleted = true;
    }
    if ($("#hide_completed").is(':checked')) {
        var hide_completed = true;
    }

    if (hide_deleted && hide_completed) { // Filter completed and deleted searches
        $.fn.dataTable.ext.search.push(
            function (settings, data, dataIndex) {
                return !data[2].includes("Status: Completed") &&
                    !data[2].includes("Status: Deleted");
            }
        )
    } else if (hide_deleted) { // Filter only deleted searches
        $.fn.dataTable.ext.search.push(
            function (settings, data, dataIndex) {
                return !data[2].includes("Status: Deleted");
            }
        )
    } else if (hide_completed) { // Filter only completed searches
        $.fn.dataTable.ext.search.push(
            function (settings, data, dataIndex) {
                return !data[2].includes("Status: Completed");
            }
        )
    } else { // Don't filter out anything
        $.fn.dataTable.ext.search.pop();
    }
}

$(document).on('click', '.add-form-row', function (e) {
    e.preventDefault();
    cloneMore('.form-row:last', 'form');
    return false;
});
$(document).on('click', '.remove-form-row', function (e) {
    e.preventDefault();
    deleteForm('form', $(this));
    return false;
});

$(document).on('change', '#id_filter_opts', function (e) {
    var selected_filter = this.value;
    var selected_filter_name = this.options[this.selectedIndex].text;
    displayFilterValues(selected_filter, null);

});


/*
Handle POST data to pre-populate the filters
*/
$(document).ready(function () {
    if ($("#post_data")[0] != undefined) {
        post_data = $("#post_data")[0].value;
        if (post_data) {
            post_data = JSON.parse(post_data);
            for (filter in post_data) {
                values = post_data[filter];
                displayFilterValues(filter, values);
            }
        }
    }
    $(".sp").selectpicker();
    $('[data-toggle="popover"]').popover();
    var table = $('#mysearches').DataTable({
        "order": [[0, "desc"]],
        "columnDefs": [
            {"width": "20%", "targets": 0},
            {"width": "50%", "targets": 1},
            {"width": "30%", "targets": 2}
        ]
    });

    //filter in column 0, with an regex, no smart filtering, no inputbox,not case sensitive
    table.column(2).search("Queued|In Progress|Preparing Results for Download|Completed|Failed", true, false).draw();


    // event listeners for hiding deleted/completed searches
    $('#hide_deleted').on('change', function () {
        var all_types = ["Queued", "In Progress", "Preparing Results for Download", "Completed", "Failed", "Deleted"];
        //build a regex filter string with an or(|) condition
        var types = $('input:checkbox[name="filter"]:checked').map(function () {
            return this.value;
        }).get()

        types = all_types.filter(function (ele1) {
            return types.indexOf(ele1) < 0;
        });

        types = types.join('|');

        //filter in column 0, with an regex, no smart filtering, no inputbox,not case sensitive
        table.column(2).search(types, true, false).draw();
    });
    $('#hide_completed').on('change', function () {
        var all_types = ["Queued", "In Progress", "Preparing Results for Download", "Completed", "Failed", "Deleted"];
        //build a regex filter string with an or(|) condition
        var types = $('input:checkbox[name="filter"]:checked').map(function () {
            return this.value;
        }).get()

        types = all_types.filter(function (ele1) {
            return types.indexOf(ele1) < 0;
        });

        types = types.join('|');

        //filter in column 0, with an regex, no smart filtering, no inputbox,not case sensitive
        table.column(2).search(types, true, false).draw();
    });

    if ($('#use_existing')[0] && $('#use_existing')[0].disabled) {
        $('#submit-search')[0].disabled = true;
        $('#mult_filter_info')[0].innerHTML = "The existing filters result in more than the allowed number of results. Please further refine your search.";
    }

    // event listener for post filter selection to disable the save search button if more than 2 are selected
    $('#post_filters').on('hidden.bs.dropdown', function () {
        var select1 = this.children[0].children[0];
        var selected1 = [];
        for (var i = 0; i < select1.length; i++) {
            if (select1.options[i].selected) selected1.push(select1.options[i].value);
        }

        // check if admin
        if (selected1.length > 1 && $('#is_admin')[0].value == 'N') {
            $('#submit-search')[0].disabled = true;
            $('#mult_filter_info')[0].innerHTML = "Please refresh your search preview to get an accurate estimate before queueing your search. Or select only one filter.";
        } else {
            $('#submit-search')[0].disabled = false;
            $('#mult_filter_info')[0].innerHTML = "";
        }
    });
});

