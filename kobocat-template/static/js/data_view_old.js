(function () {
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this;

    // Check if the `FH` namespace already exists and create it otherwise. We'll
    // attach all our exposed objects to it.
    var FH = root.FH = root.FH || {};
    var FHoptions = FH.FHoptions;
    var globalDataTableView;
    // Map of FH types to Backgrid cell types
    var FHToBackgridTypes = {
        'integer': 'integer',
        'decimal': 'number',
        /*'select': '',
         'select all that apply': '',
         'select one': '',*/
        'photo': '',
        'image': '',
        'date': 'date',
        'datetime': 'datetime'
    };

    var PageableDataset = FH.PageableDataset = Backbone.PageableCollection.extend({
        state: {
            pageSize: 50
        },
        mode: "client", // page entirely on the client side,
        model: FH.Data,
        initialize: function (models, options) {
            // set the url
            /*if(! options.url) {
             throw new Error(
             "You must specify the dataset's url within the options");
             }*/
            this.url = options && options.url;

            // Call super
            return Backbone.PageableCollection.prototype.initialize.apply(this, arguments);
        }
    });

    var NameLabelToggle = Backbone.View.extend({
        className: 'table-control-container label-toggle-container',

        template: _.template('' +
            '<span>' +
            '<label class="checkbox">' +
            '<input class="name-label-toggle" type="checkbox" name="toggle_labels" aria-controls="data-table" <% if (isChecked) { %>checked="checked" <% } %> />' +
            ' Toggle between choice names and choice labels' +
            '</label>' +
            '</span>'),

        events: {
            'click .name-label-toggle': "toggleLabels"
        },

        render: function () {
            this.$el.empty().append(this.template({
                isChecked: false
            }));
            this.delegateEvents();
            return this;
        },

        toggleLabels: function (e) {
            var enabled = !!$(e.currentTarget).attr('checked');
            this.trigger('toggled', enabled);
        }
    });

    var ClickableRow = Backgrid.Row.extend({
        highlightColor: 'lightYellow',
        events: {
            'dblclick': 'rowDoubleClicked'
        },
        initialize: function (options) {
            return Backgrid.Row.prototype.initialize.apply(this, arguments);
        },
        rowDoubleClicked: function (evt) {
            var record_id = this.model.get("_id");
            if (record_id) {
                window.open(instance_view_url + "#/" + record_id, "_blank");
            }
        }
    });

    var searchButton = Backbone.View.extend({
        tagName     : "div",
        className     : "my-buttons",
        template     : null,

        //we listen for clicks on items with the css class "button"
        events : {
          "click .button" : "buttonClickHandler"
        },
       
        initialize : function(){
          //_.bindAll(this);

          //here we simulate that we load an external template with the Html of our view
          this.template = _.template('<input class="button" type="button" value="Search">');

        },

        render : function(){

          this.$el.html( this.template() );

          $('.filters').append(this.$el);
         
            return this;
        },

        buttonClickHandler : function(event){
//          var fromdate = $( "input[id='fromDate']" ).val();
//          fromdate = fromdate.replace(" ","T");
//          var todate = $( "input[id='toDate']" ).val();
//          todate = todate.replace(" ","T");
//          globalDataTableView.data.url = FHoptions.dataUrl+'?query={"_submission_time":{"$gte":"'+fromdate+'","$lt":"'+todate+'"}}';
            var query = getQuery();
            globalDataTableView.data.url = FHoptions.dataUrl+'?query='+query;
            // console.log(globalDataTableView.data.url);
            var form = globalDataTableView.form;
            globalDataTableView.form.load();
            return false;
        }
    });

    var DataTableView = FH.DataTableView = Backbone.View.extend({
        // Instance of the `Form` object
        form: void 0,

        // Instance of the `Data` object
        data: void 0,

        // Whether to show header names or labels
        showHeaderLabels: false,

        // Whether to show select names or labels
        showLabels: false,

        initialize: function (options) {
            FHoptions = options;
            // console.log(options);
            var paginator;
            var filter;
            var dataGrid;
            var datePick2;
            var datePick1;
            if (!options.formUrl) {
                throw new Error("You must define a formUrl property within options");
            }

            if (!options.dataUrl) {
                throw new Error("You must define a dataUrl property within options");
            }

            // Setup the form
            this.form = new FH.Form({}, {url: options.formUrl});

            // Setup the data
            this.data = new FH.PageableDataset([], {
                // mpower add : passing query for initial data load, with only
                // data submitted by users whose data current user can view
                url: options.dataUrl+'?query='+initial_query
                // url: options.dataUrl
            });

            // Initialize the header name/label toggle
            var headerLangSwitcher = new NameLabelLanguagePicker({
                label: "Column Headers",
                model: this.form
            });

            // Initialize the data name/label toggle
            var dataLangSwitcher = new NameLabelLanguagePicker({
                label: "Answer Values",
                model: this.form
            });

            var searchButtonTest = new searchButton({
                label: 'Search',
                model : this.form
            });
            this.form.on('load', function () {
                var dataTableView = this;

                // Initialize the data
                this.data.on('load', function () {

                    // Disable this callback - infinite loop
                    // mpower comment below line
                    //this.data.off('load');

                    // Append the toggle labels checkbox
                    $(this.labelToggleTemplate({isChecked: this.showLabels})).insertAfter(this.$('.dynatable-per-page'));

                    this.delegateEvents({
                        'click input.toggle-labels': 'onToggleLabels'
                    });
                }, this);

                // Initialize the grid
                if(dataGrid==null || dataGrid=='undefined') {
                    this.dataGrid = new Backgrid.Grid({
                        row: ClickableRow,
                        className: 'backgrid table table-striped table-hover',
                        columns: this.form.fields.map(function (f) {
                            var column = {
                                name: f.get(FH.constants.XPATH),
                                label: f.get(FH.constants.NAME),
                                editable: false,
                                cell: "string"//FHToBackgridTypes[f.get(FH.constants.TYPE)] || "string"
                            };
                            if (f.isA(FH.types.SELECT_ONE) || f.isA(FH.types.SELECT_MULTIPLE)) {
                                column.formatter = {
                                    fromRaw: function (rawData) {
                                        return DataTableView.NameOrLabel(f, rawData, dataTableView.showLabels, dataTableView.form.get('language'));
                                    }
                                };
                            }
                            if (f.isA(FH.types.INTEGER) || f.isA(FH.types.DECIMAL)) {
                                column.sortValue = function (model, fieldId) {
                                    var func = FH.ParseFunctionMapping[f.get(FH.constants.TYPE)];
                                    return FH.DataSet.GetSortValue(model, fieldId, func);
                                }
                            }
                            return column;
                        }),
                        collection: this.data
                    });
                    dataGrid = this.dataGrid;
                //======================= ENDING:new code==========================================
                }else{
                    this.dataGrid.collection=this.data;
                }

                this.$el.append(this.dataGrid.render().$el);

                // Initialize the paginator
                if(paginator==null || paginator=='undefined') {
                    paginator = new Backgrid.Extension.Paginator({
                        collection: this.data
                    });
                } else {   
                    paginator.collection=this.data;
                }

                // Render the paginator
                this.$el.append(paginator.render().$el);

                // Initialize a client-side filter to filter on the client
                // mode pageable collection's cache.
                if(filter==null || filter=='undefined') {
                    filter = new Backgrid.Extension.ClientSideFilter({
                        collection: this.data.fullCollection
                    });
                } else {
                    filter.collection=this.data.fullCollection;
                }

                // Render the filter
                this.$el.prepend(filter.render().$el);

                // Add some space to the filter and move it to the right
                filter.$el.css({float: "right", margin: "20px"});

                // catch the `switched` event
                dataLangSwitcher.on('switch', function (language) {
                    // if the new language is `0`, we want to show xml values, otherwise, we want labels in whatever language is specified
                    this.showLabels = language !== '-1';
                    // set the language if we're showing labels
                    if (this.showLabels) {
                        this.form.set({language: language}, {silent: true});
                    }
                    this.dataGrid.render();
                }, this);

                this.$el.prepend(dataLangSwitcher.render().$el);

                // catch the `switched` event
                headerLangSwitcher.on('switch', function (language) {
                    // if the new language is `0`, we want to show xml values, otherwise, we want labels in whatever language is specified
                    this.showHeaderLabels = language !== '-1';
                    // set the language if we're showing labels
                    this.form.set({header_language: language});
                }, this);

                this.$el.prepend(headerLangSwitcher.render().$el);

                // only add the language picker if we have multiple languages
                if (this.form.get('languages') && this.form.get('languages').length > 1) {
                    // Initialize the language selector
                    var languagePicker = new FH.LanguagePicker({
                        model: this.form,
                        className: 'table-control-container language-picker-container'
                    });

                    languagePicker.render().$el.insertBefore(this.$('.label-toggle-container'));
                }
                        this.$el.prepend(headerLangSwitcher.render().$el);
                        
                        
                //      var fromdate = $( "input[id='fromDate']" ).val();
                //      var todate = $( "input[id='toDate']" ).val();
                //
                //
                //      datePicker2.$el.css({float: "right", margin: "5px"});
                //      this.$el.prepend(datePicker2.render().$el);
                //      $( "input[id='fromDate']" ).val(fromdate);
                //
                //      datePicker1.$el.css({float: "right", margin: "5px"});
                //      this.$el.prepend(datePicker1.render().$el);
                //      $( "input[id='toDate']" ).val(todate);

                // console.log('datePick2');
                // console.log(datePicker2.value);
                // console.log('datePick1');
                // console.log(datePicker1.value);

               // searchButtonTest.$el.css({float: "right", margin: "30px"});
               // this.$el.prepend(searchButtonTest.render().$el);
                // Fetch some data
                var base_url = window.location.protocol+"//"+window.location.host + "/media/" ;
                var image_list = [];
                this.data.fetch({reset: true}).promise().done(function(data){
                    data.forEach(function(submission) {
                        submission._attachments.forEach(function(attachment) {
                            var image_path = base_url + attachment.filename ;
                            var image_name_index = attachment.filename.lastIndexOf("/") + 1;
                            var image_name = attachment.filename.substring(image_name_index);
                            var image_object = {'image_name':image_name,'image_path':image_path};
                            image_list.push(image_object);
                        });
                    });
                    generate_gallery(image_list);
                });
            }, this);

            // Catch language change events
            this.form.on('change:header_language', function (model, language) {
                var dataTableView = this;
                if (this.dataGrid) {
                    this.dataGrid.columns.each(function (column) {
                        var label,
                            field = dataTableView.form.fields
                                .find(function (f) {
                                    return f.get(FH.constants.XPATH) === column.get('name');
                                });

                        if (dataTableView.showHeaderLabels) {
                            label = field.get(FH.constants.LABEL, language);
                        } else {
                            label = field.get(FH.constants.NAME);
                        }
                        column.set({'label': label});
                    });
                    this.dataGrid.header.render();
                }
            }, this);

            this.form.load();
            globalDataTableView = this;
        }
    });

    var NameLabelLanguagePicker = Backbone.View.extend({
        label: void 0,

        className: 'table-control-container',

        template: _.template(
            '<label><%= label %></label><select><% _.each(languages, function(lang){ %>' +
                '<option value="<%= lang["name"] %>"><%= lang["value"] %></option> ' +
            '<% }); %></select>'),

        events: {
            'change select': function (evt) {
                var value = $(evt.currentTarget).val() || undefined;
                this.trigger('switch', value);
            }
        },

        initialize: function (options) {
            this.label = options.label || "&nbsp;";
            Backbone.View.prototype.initialize.apply(this, arguments);
        },

        render: function () {
            var languages = NameLabelLanguagePicker.LanguagesForSelect(
                this.model);
            this.$el.empty().append(this.template({
                languages: languages,
                label: this.label
            }));
            return this;
        }
    });

    NameLabelLanguagePicker.LanguagesForSelect = function (model) {
        var languages = model.get('languages').length == 0?
            [{name: null, value: 'Show Labels'}]:
            model.get('languages').map(
                function(lang){
                    return {name: lang, value: "Show Labels in " + lang};
                });
        languages.unshift({name: '-1', value: 'Show XML Values'});
        return languages
    };

    // Used by select formatters to return wither name the name or label for a response
    DataTableView.NameOrLabel = function (field, value, showLabels, language) {
        var xpath,
            choices,
            selections,
            results;

        // if showLabels === true, get the label for the selected value(s)
        if (showLabels) {
            choices = new FH.FieldSet(field.get(FH.constants.CHILDREN));

            // Split the value on a space to get a list for multiple choices
            selections = value && value.split(' ') || [];
            results = [];

            _.each(selections, function (selection) {
                var choice = choices.find(function (c) {
                    return c.get(FH.constants.NAME) === selection;
                });
                if (choice) {
                    results.push(choice.get(FH.constants.LABEL, language));
                }
            });
            return results.join(', ');
        } else {
            return value;
        }
    };
}).call(this);

function getQuery() {
    var query = ' {"$and" : [ ';
    var partial_query = "";
    var from = document.getElementById("start_date").value  ;
    var to  = document.getElementById("end_date").value ;
    
    if (!((!from || 0 === from.length) || (!to || 0 === to.length))) {
        from += "T00:00:00";
        to += "T23:59:59" ;
        partial_query = '{"_submission_time":{"$gte":"'+from+'","$lte":"'+to+'"}}';
        query += partial_query + ',' ;
    }

    var selected_user = document.getElementById("userlist").value  ;
    if ( selected_user !== 'custom') {
        partial_query = '{"_submitted_by":"'+selected_user+'"}'
        query += partial_query + ',' ;
    }else{
        if( allowed_users > 0 ){
            query += '{"_submitted_by": { "$in" : ' + formatted_list + ' }'  + ' },' ;      
        }            
    }
    query += "] }" ;
    var lastCommaIndex = query.lastIndexOf(",");
    query = query.replaceAt(lastCommaIndex, " ");
    return query;
}

// function getQuery(){
//     var query = ' {"$and" : [ ';
//     $('#filter-table tr td:nth-child(2)').each(function(){
//         var row_id = $(this).attr("id");
//         var count = row_id.charAt(row_id.length-1);
//         var partial_query = "";
//         if(count == 0){
//             var from = document.getElementById("start_date").value  ;
//             var to  = document.getElementById("end_date").value ;

//             if (!((!from || 0 === from.length) || (!to || 0 === to.length))) {
//                 from += "T00:00:00";
//                 to += "T23:59:59" 
//                 partial_query = '{"_submission_time":{"$gte":"'+from+'","$lte":"'+to+'"}}'
//                 query += partial_query + ',' ;
//             }
//         }else if (count == 1){
//             var selected_user = document.getElementById("userlist").value  ;
//             if ( selected_user !== 'custom') {
//                 partial_query = '{"username":"'+selected_user+'"}'
//                 query += partial_query + ',' ;
//             }else{
//                 if( allowed_users > 0 ){
//                     query += initial_query  + ',' ;      
//                 }            
//             }
//         }else{
//             var key_id = "criteria_key"+count ;
//             var value_id = "criteria_value"+count ;
//             var element = document.getElementById(value_id) ;
//             if(element !== null){
//                 //check input types
//                 if(element.tagName === 'SELECT') {
//                     if($(element).attr("multiple")){
//                             var key = document.getElementById(key_id).value;
//                             var value = "";
//                             var is_selected_any = false ;
//                             var partial_query = '{"$or": [ ';
//                             for (var i = 0; i < element.options.length; i++) {
//                                if(element.options[i].selected){
//                                     is_selected_any = true ;
//                                     partial_query += '{"'+key+'":{ "$regex" : "'+element.options[i].value +'"}},';
//                                 }
//                             }
//                             partial_query += "] }" ;
//                             var lastCommaIndex = partial_query.lastIndexOf(",");
//                             partial_query = partial_query.replaceAt(lastCommaIndex, " ");
//                             if (is_selected_any) {
//                                 query += partial_query + ',';    
//                             }
//                     }else{
//                         var key = document.getElementById(key_id).value;
//                         if(has_value(element)){
//                             var value = element.value;
//                             partial_query = '{"'+key+'":"'+value+'"}';
//                             query += partial_query + ',' ;    
//                         }    
//                     }
//                 }else if(element.tagName === 'INPUT' && element.type === 'text') {
//                     var key = document.getElementById(key_id).value;
//                     if(has_value(element)){
//                         var value = element.value;
//                         partial_query = '{"'+key+'":"'+value+'"}';
//                         query += partial_query + ',' ;    
//                     }
                    
//                 }else if(element.tagName === 'INPUT' && element.type === 'number' && element.step ==="any") {
//                     var key = document.getElementById(key_id).value;
//                     if(has_value(element)){
//                         var value = element.value;
//                         if(value % 1 === 0){
//                             value = (parseFloat(value)).toFixed(1);
//                             element.value = String(value);
//                         }
//                         partial_query = '{"'+key+'":"'+value+'"}';
//                         query += partial_query + ',' ;    
//                     }
//                 }else if(element.tagName === 'INPUT' && element.type === 'number' && element.step ==="1") {
//                     var key = document.getElementById(key_id).value;
//                     if(has_value(element)){
//                         var value = Math.floor(element.value);
//                         element.value = value ;
//                         partial_query = '{"'+key+'":"'+value+'"}';
//                         query += partial_query + ',' ;    
//                     }
//                 }            
//             }
//         }
//     })
//     query += "] }" ;
//     var lastCommaIndex = query.lastIndexOf(",");
//     query = query.replaceAt(lastCommaIndex, " ");
//     if(query.length <= 17){
//         query = "{}"   
//     }
//     return query;
// }


function contains(a, obj) {
    var i = a.length;
    while (i--) {
       if (a[i] === obj) {
           return true;
       }
    }
    return false;
}

function has_value(element) {
    var value = element.value;
    if(!value || 0 === value.length){
        return false;    
    }else{
        return true;    
    }
    return false;
}


String.prototype.replaceAt=function(index, character) {
    return this.substr(0, index) + character + this.substr(index+character.length);
}
