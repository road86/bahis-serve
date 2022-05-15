var dataSet = [];
var chartSeries = [];
function isArray(what) {
    return Object.prototype.toString.call(what) === '[object Array]';
}

function initDataTable(tableID, dataSet, tableColumn) {
    if (tableColumn.length == 0) {
        tableColumn = ["id", "user_id", "received", "pngo", "approvalstatus", "details"];
    }
    var query_column = []
    for (var column in tableColumn) {
        query_column.push({
            title: tableColumn[column]
        });

    }
    // Disable search and ordering by default
    $.extend($.fn.dataTable.defaults, {
        searching: true,
        ordering: true
    });
    if ($.fn.dataTable.isDataTable('#' + tableID)) {
        var data_table = $('#' + tableID).DataTable();
        data_table.clear().draw();
        data_table.rows.add(dataSet); // Add new data
        data_table.columns.adjust().draw(); // Redraw the DataTable
    } else {
        $('#' + tableID).DataTable({
            data: dataSet,
            // scrollY: 400,
            "columnDefs": [{
                className: "dt-body-center",
                "targets": "_all"
            }],

            scrollY: 400,
            scrollX: true,
            scrollCollapse: true,
            paging: true,
            columns: query_column
        });
        $('.dataTables_scrollHeadInner').css('width','auto');
    }
    $('#' + tableID + '_wrapper .dataTables_filter input').addClass("form-control input-medium"); // modify table search input
    $('#' + tableID + '_wrapper .dataTables_length select').addClass("form-control"); // modify table per page dropdown
}

function get_query_data(data_url, needfilter, filter_data, form_id_string,dateColumn) {
    var SendInfo = {
        'filter': '0'
    };
    var data_to_send = SendInfo;

    if (needfilter) {
        data_to_send = filter_data;
    }
    console.log("data_url:::::::::::::::::"+data_url)
    ///fetch data json.
    $.ajax({
        url: data_url,
        type: 'GET',
        data: data_to_send,
        dataType: 'json',
        success: function(response) {
            response.data.sort(function(a, b) {
                return new Date(b[2]).getTime() - new Date(a[2]).getTime()
            });
            var byStatus = filterByProperty(response.data, 4, 'New');
            initDataTable("pending_table", byStatus, response.col_name);
            initDataTable("example", response.data, response.col_name);
            chartSeries = generateChartData(response.data,dateColumn)
            //createChartData(chartSeries,form_id_string,'chart-main-container',7,'column');
        },
        error: function() {
            alert("error");
        }
    });
}

function filterByProperty(array, prop, value) {
    var filtered = [];
    for (var i = 0; i < array.length; i++) {
        var obj = array[i];
        if (obj[prop] == value) {
            filtered.push(obj);
        }
    }
    return filtered;
}


function generateChartData(data,dateColumn){
    var chartSeries = [];
    var allExistingDateData = getCount(data,dateColumn);
    var lastSixtyDays = lastDays(60);
    for(var i=0;i<60;i++){
        if(!(lastSixtyDays[i] in allExistingDateData)){
            chartSeries.push(0);
        } else {
            chartSeries.push(allExistingDateData[lastSixtyDays[i]]);
        }
    }
    return chartSeries;
}


function pad(n) {
  return n.toString().length == 1 ? '0' + n : n;
}

function getCount(arr,dateColumn) {
  var obj = {};
  for (var i = 0, l = arr.length; i < l; i++) {
    var thisDate = new Date(arr[i][dateColumn]);
    var day = pad(thisDate.getDate());
    var month = pad(thisDate.getMonth() + 1);
    var year = thisDate.getFullYear();
    var key = [year, month, day].join('-');
    obj[key] = obj[key] || 0;
    obj[key]++;
  }
  return obj;
}

function formatDate(date){
    var dd = date.getDate();
    var mm = date.getMonth()+1;
    var yyyy = date.getFullYear();
    if(dd<10) {dd='0'+dd}
    if(mm<10) {mm='0'+mm}
    date = yyyy+'-' + mm + '-'+dd;
    return date
 }

function lastDays (n) {
    var result = [];
    for (var i=0; i<n; i++) {
        var d = new Date();
        d.setDate(d.getDate() - i);
        result.push( formatDate(d) )
    }

    return(result);
}
