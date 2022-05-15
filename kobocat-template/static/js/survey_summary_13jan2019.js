var days = ['Sunday','Monday','Tuesday','Wednesday', 'Thursday','Friday','Saturday'];
var series_val = [];
var today = 0;
var yesterday = 0;
var lastSubmission = 'recent';
var total_json_array = [];
//var drilldownSubArray = [];

(function (H) {
        H.wrap(H.Legend.prototype, 'colorizeItem', function (proceed, item, visible) {
        	item.legendColor = item.options.legendColor;
            proceed.apply(this, Array.prototype.slice.call(arguments, 1));
        });
    }(Highcharts));

function createChart(container,processed_json)
{    
     var options =   {
	credits: {
	      enabled: false
	  },
        chart: {
            type: 'column',
            renderTo: container
        },
        title: {
            text: 'Submission of last 7 Days'
        },
        xAxis: {
            categories: [
                    'Sun','Mon','Tue','Wed','Thu','Fri','Sat'
                ]
        },
         yAxis: {
                min: 0,
                title: {
                    text: 'Submission per day (No.)'

                }
            },
        plotOptions: {
            column:{
                colorByPoint: true
            },
            series: {
                legendColor: '#e02222',
                stacking: 'normal',
                dataLabels: {
                    enabled: false,
                    style: {
                        textShadow: '0 0 3px black'
                    }
                }, point: {
                       events: {
                           click: function () {
                               alert('Category: ' + this.category + ', value: ' + this.y);
                           }
                       }
                   }
               }

            },
            colors: ['#e02222'],
            tooltip: {
                headerFormat: '<span style="font-size:10px">{point.key}</span><table>',
                pointFormat: '<tr><td style="color:{series.color};padding:0">{series.name}: </td>' +
                    '<td style="padding:0"><b>{point.y:.1f} </b></td></tr>',
                footerFormat: '</table>',
                shared: true,
                useHTML: true
            },

        series: [{
                name: container,
                data: processed_json

                }]

    };

    chart = new Highcharts.Chart(options);
}


var date_sort_asc = function (date1, date2) {
  // This is a comparison function that will result in dates being sorted in
  // ASCENDING order. As you can see, JavaScript's native comparison operators
  // can be used to compare dates. This was news to me.
  if (date1 > date2) return 1;
  if (date1 < date2) return -1;
  return 0;
};

function createTableRow(dataObj,submission,jsondata,title, ownership,form_permission){
    var jsonObj = JSON.parse(jsondata);
    var jsonOwner = JSON.parse(ownership);
    var jsonPerm = JSON.parse(form_permission);
    var length = 0;
    var permission_arr = jsonPerm[dataObj];
    var processed_json = new Array();
    var yesterdayDate = new Date(currentDate);
    var currentDate = new Date();
    if(jsonObj[dataObj][0] == 'no submission'){
        length = 0;
    }else{
        length = jsonObj[dataObj].length;
    }
    series_val.length = 0;
    series_val = Array.apply(null, Array(7)).map(Number.prototype.valueOf,0);
    series_val_total = Array.apply(null, Array(length)).map(Number.prototype.valueOf,0);

    //create array for total submission chart
    total_json_array.push({
                name: title,
                y: length,
                drilldown: dataObj,
             });

     today = 0;
     this_month = 0;

     yesterdayDate.setDate(currentDate.getDate() - 1);
     var dates=[];
    // Populate series
    for (i = 0; i < length; i++) {
        var d = new Date(jsonObj[dataObj][i]);
        var isToday = (d.toDateString() == currentDate.toDateString());
        var isThisMonth = (d.getMonth() == currentDate.getMonth());
        if (isToday)
          today+=1;
        if (isThisMonth)
          this_month+=1;
        series_val[d.getDay()]+= 1;
        series_val_total[d.getDay()] +=1;
        dates.push(d);
    }

    /*drilldownSubArray.push({
        name: title,
        id: dataObj,
        data: series_val_total
    });*/

    var maxDate = new Date(Math.max.apply(null,dates));

    if (maxDate == 'Invalid Date')
      maxDate = 'N/A';
    else
      maxDate = maxDate.toDateString();

    var projectSettings = '';
    var roleSettings = '';
    var newSubmission = '';
    var details = '';
    var edit = '';
    var operation_status = '';
    var isOwner = jsonOwner[dataObj][0];
    var rqst_user = jsonOwner[dataObj][2];
    var arrayLength = permission_arr.length;
    var Can_View = false;
    var Can_submit = false;
    var Can_edit = false;

    for (var i = 0; i < arrayLength; i++) {
        var perm_info = permission_arr[i].split("|");
        if(perm_info[0] == rqst_user){

          if(perm_info.indexOf("Can View") > -1)
            Can_View  =  true;
          if(perm_info.indexOf("Can submit to") > -1)
            Can_submit = true;
          if(perm_info.indexOf("Can Edit") > -1)
            Can_edit = true;
        }
      }
console.log(isOwner+'--'+dataObj+'Can_View::'+Can_View+'Can_submit::'+Can_submit+'Can_edit::'+Can_edit);

    if ( isOwner ) {
	    roleSettings = '<a href="/usermodule/'+jsonOwner[dataObj][1]+'/forms/'+dataObj+'/'+'role_form_map'+'" class="btn red btn-md" type="button"> Permissions </a>';
        projectSettings = '<a href="/'+jsonOwner[dataObj][1]+'/forms/'+dataObj+'/'+'form_settings'+'" class="btn red btn-md" type="button"> Settings </a>';
	    edit = '<a href="'+jsonOwner[dataObj][1]+'/form_replace/'+dataObj+'/" class="btn red btn-md" type="button"> Edit </a>';
	    schedule = '<a href="'+jsonOwner[dataObj][1]+'/form_schedule/'+dataObj+'/" class="btn red btn-md" type="button"> Schedule </a>';
      }
    if (Can_View){
      details = '<a href="/usermodule/'+jsonOwner[dataObj][1]+'/projects-views/' + dataObj + '/" class="btn red btn-md" type="button"> Details </a>';
    }
    if(Can_submit){
       newSubmission = '<a href="/'+jsonOwner[dataObj][1]+'/'+'forms'+'/'+dataObj+'/'+'enter-data'+'" target="_blank" class="btn red btn-md" type="button">New Submission</a>';
    }

    operation_status = '<a class="proj_submission" href="/approve-status/operational-status/"> Op-Status </a>';
    var table = $('#tg-xY4Sf');
    var spDataTableRow = $('<tr></tr>');
    var spTableRowData = $('<td class="tg-yw4l">'+title + '</td><td>'+dataObj+ '</td><td>'+details+' '+ projectSettings +' '   + roleSettings +' ' + edit+' ' + schedule + '</td>');

    spDataTableRow.append(spTableRowData);
    table.append(spDataTableRow);
    //createChart(dataObj,series_val);
}

function pageReloadWithStatus(param_str){

    $.ajax({
      url:'/{{ user.username }}/sendmessage',
      type:'POST',
      data: param_str,
      dataType: 'json',
      success: function( json ) {
        alert(json.send);
      },
    });
}

function popupEnterMessage() {
    subscribeID = document.getElementById('subscribeid').value;
    msg = document.getElementById('msg').value;
    if (msg != null && subscribeid != null) {
        var param_data = {
            'subscribeid':subscribeID,
            'delivermsg':msg,
        }
        pageReloadWithStatus(param_data);
    }
}

function showpopup()
{
   $("#msgform").fadeIn();
   $("#msgform").css({"visibility":"visible","display":"block"});
}

function hidepopup()
{
   $("#msgform").fadeOut();
   $("#msgform").css({"visibility":"hidden","display":"none"});
}

$(function () {
    // Create the chart
    /*Highcharts.chart('submissions_statistics', {
        chart: {
            type: 'column'
        },
        credits: {
	      enabled: false
	    },
        title: {
            text: 'Total Submissions'
        },
        subtitle: {
            text: 'Click the columns to view date-wise submissions'
        },
        xAxis: {
            type: 'category'
        },
        yAxis: {
            title: {
                text: 'Total submissions'
            }

        },
        legend: {
            enabled: false
        },
        plotOptions: {
            series: {
                borderWidth: 0,
                dataLabels: {
                    enabled: true,
                }
            }
        },

        tooltip: {
            headerFormat: '<span style="font-size:11px">{series.name}</span><br>',
            pointFormat: '<span style="color:{point.color}">{point.name}</span>: <b>{point.y:.0f}</b> submissions<br/>'
        },

        series: [{
            name: 'Forms',
            colorByPoint: true,
            data: total_json_array
        }]
    });*/
});
