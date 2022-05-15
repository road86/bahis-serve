Question = function(questionData) {
    this.name = questionData.name;
    this.type = questionData.type;
    this.label = questionData.label;
    this.children = questionData.children;
}

Choice = function(choicesData) {
    this.name = choicesData.name;
    this.label = choicesData.label;
}

Question.prototype.getLabel = function(language) {
    /// if plain string, return
    if (typeof(this.label) == "string"){
        return this.label;
    }
    else if (typeof(this.label) == "object") {
        if (language && this.label.hasOwnProperty(language)){
            return this.label[language];
         } else {
            var label = null;
            for (key in this.label) {
                label = this.label[key];
                break; // break at first instance and return that
            }
            return label;
        }

    }

    return this.name;
}

function isArray(what) {
    return Object.prototype.toString.call(what) === '[object Array]';
}

function parseChoices(choices) {
    questionChoices = choices;
}


function parseQuestions(children, prefix, cleanReplacement) {
    var idx;
    cleanReplacement = typeof cleanReplacement !== 'undefined' ? cleanReplacement : '_';
    for (idx in children) {
        var question = children[idx];
            questions[((prefix ? prefix : '') + question.name)] = new Question(question);
    }
}

function replaceLabel(label,keyValArr){
    var newLabel = '';
    if(label.match(/\${([^}]+)}/g)){
        var subLabel = label.match(/\${([^}]+)}/g);
        var cleanRepKey = subLabel[0].slice(2,(subLabel[0].length-1));
        var cleanRepValue = keyValArr[cleanRepKey];
        newLabel = label.replace(subLabel[0], cleanRepValue);
    } else {
        newLabel = label;
    }

    return newLabel;
}

function addOrEditNote() {
    var instance_id = $("#instance_id").val();
        note = $("#note").val().trim();
    if (note == "") {
        return false;
    }
    var notes_url = '/api/v1/notes',
        post_data = {
            'note': note,
            'instance': instance_id
        };
    if ($("#notesform #note-id").val() != undefined) {
        // Edit Note
        post_data.pk = $("#notesform #note-id").val();
        notes_url += "/" + post_data.pk;
        
        $.ajax({
            url: notes_url,
            type: "PUT",
            data: post_data,
            statusCode: {
                404: function() {
                    alert("Note \"" + note + "\" not found or already deleted.");
                    app.refresh();
                }
            }
        }).done(function(data) {
            $("#notesform")[0].reset();
            $("#notesform #note-id").remove();
            app.refresh();
        });
    } else {
        // Add New Note
        $.post(notes_url, post_data).done(function(data) {
            $("#notesform")[0].reset();
            app.refresh();
        }).fail(function(data) {

        })
    }
    return false;
}


function parseLanguages(children) {
    // run through question objects, stop at first question with label object and check it for multiple languages
    for (questionName in children) {
        var question = children[questionName];
        if (question.hasOwnProperty("label")) {
            var labelProp = question["label"];
            if (typeof(labelProp) == "string")
                languages = ["default"];
            else if (typeof(labelProp) == "object") {
                for (key in labelProp) {
                    languages.push(key)
                }
            }
            break;
        }
    }
    if (languages.length == 0) {
        languages.push('en');
    }
}

function replaceAll(str, find, replace) {
  return str.replace(new RegExp(find, 'g'), replace);
}

function createTable(canEdit,datavals) {
    var keyValArr = {};
    var dataContainer = $('#data');
    dataContainer.empty();
    if (languages.length > 1) {
        var languageRow = $('<div class="row"></div>');
        var languageStr = $('<div class="span6"><span>' + gettext("Change Language:") + '</span> </div>');
        var languageSelect = $('<select class="language"></select>');
        var i;
        for (i = 0; i < languages.length; i++) {
            var language = languages[i];
            var languageOption = $('<option value="' + i + '">' + language + '</opton>');
            languageSelect.append(languageOption);
        }
        languageStr.append(languageSelect);
        languageRow.append(languageStr);
        dataContainer.append(languageRow);
    }

    // status and navigation rows - have to separate top and bottom since jquery doesnt append the same object twice
    var topStatusNavRows = $('<div class="row"></div>');
    var statusStr = '<div class="col-md-6"><div class="dataTables_info"><h4 class="record-pos">' + gettext("Record 1 of 6") + '</h4></div></div>';
    var topStatus = $(statusStr);
    //topStatusNavRows.append(topStatus);

    var pagerStr = '<div class="col-md-6"><ul class="pager"><li class="prev previous"><a href="#">← ' + gettext("Previous") + '</a></li><li class="next"><a href="#">' + gettext("Next") + ' →</a></li></ul>';
    //var topPager = $(pagerStr);

    //topStatusNavRows.append(topPager);
    dataContainer.append(topStatusNavRows);

    if (canEdit === true) {
        var specificEditDelete = '<a target="_blank" id="title_edit" href="#kate" class="btn red bind-edit disabled">' + gettext("edit") + '</a>&nbsp;<a href="#"class="btn red btn-danger">' + gettext("Delete") + '</a>&nbsp;';
    } else {
        var specificEditDelete = '';
    }

    var editDelete = '<div class="row"><div class="col-md-6" style="">'+specificEditDelete+'<a onclick="printMe();" class="btn "></a></div></div><div class="top-buffer-min">';
    dataContainer.append(editDelete);

    var notesSection = '<div id="notes" style="display: none;"><form action=" onsubmit="return addOrEditNote()" method="post" name="notesform" id="notesform"><input type="hidden" value="" name="instance_id" id="instance_id" /><div class="controls"><textarea id="note" class="form-control" rows="2" name="note" placeholder="' + gettext("Add note to instance") + '" autocomplete="off" style="width: 100%"></textarea></div><div class="controls controls-row"><div class="top-buffer-min"><button type="submit" id="note_save" class="btn green" style="" >' + gettext("Save note") + '</button></div></form><div id="notes-section"></div></div><div class="top-buffer">';
    dataContainer.append(notesSection);

    if(approvedef.length>0){
    var statusApproveSection = '<div class="col-md-2"><select class="form-control" id="status_approve" name="status_approve"></select></div><button onclick="updateARStatus('+instance_id+')" class="btn red">Update Status</button>';
    dataContainer.append(statusApproveSection);
    
    for (idx in approvedef){
                console.log(approvedef[idx].ns_value);
		$("#status_approve").append( $('<option></option>').val(approvedef[idx].ns_value).html(approvedef[idx].ns_label));
	    }
}

    var table = $('<table style="display: none;" id="data-table" class="table table-bordered table-striped"></table');
    var tHead = $('<thead><tr><th width="50%">' + gettext("Question") + '</th><th>' + gettext("Response") + '</th></tr></thead>');
    var tBody = $('<tbody></tbody>');
    var key;
    //console.log(questions);
    for (key in questions) {
        var question = questions[key];
        if(question.type != 'note'){
            var tdLabel = $('<td></td>');
            var idx;
            var responseData = '';
            for (idx in languages) {
                var language = languages[idx];
                var label = question.getLabel(language);
                label = replaceLabel(label,keyValArr);
                var style = "display:none;";
                var spanLanguage = $('<span class="language language-' + idx + '" style="' + style + '">' + label + '</span>');
                tdLabel.append(spanLanguage);
            }
            if(question.type == 'repeat'){
            var childQuestions = {};
                for (yzx in question.children) {
                    var cQuestion = question.children[yzx];
                        childQuestions[(cQuestion.name)] = new Question(cQuestion);
                }
                responseData = '<table class="table table-bordered">';
                for(var tdx in datavals[key]){
                    responseData += '<tr><th colspan="2"></th></tr>';
                    for(ptx in datavals[key][tdx]){

                        var repeatLabel = ptx.replace(key+'/','');
                        //console.log(repeatLabel)
                        if(typeof childQuestions[repeatLabel] == 'undefined'){

                        } else {
                            //responseData += '<tr><td>'+childQuestions[repeatLabel].getLabel()+'</td><td>'+datavals[key][tdx][ptx]+'</td></tr>';
                            responseData += '<tr><td>';
                            for (var index in languages) {
                                responseData += '<span class="language language-'+index+'" style="display:none;">'+childQuestions[repeatLabel].getLabel(languages[index])+'</span>';
                            }
                            responseData += '</td><td>'+datavals[key][tdx][ptx]+'</td></tr>';
                        }
                    }
                }
                responseData += '</table>';
            } else if (question.type == 'group') {
                var childQuestions = {};
                for (yzx in question.children) {
                    var cQuestion = question.children[yzx];
                        childQuestions[(cQuestion.name)] = new Question(cQuestion);
                }
                responseData = '<table class="table table-bordered">';
                for(cdx in datavals){
                    if(cdx.indexOf(key+'_') != -1){
                        var repeatLabel = cdx.replace(key+'_','');
                        if(typeof childQuestions[repeatLabel] != 'undefined'){
                            responseData += '<tr><td>';
                            for (var index in languages) {
                                responseData += '<span class="language language-'+index+'" style="display:none;">'+childQuestions[repeatLabel].getLabel(languages[index])+'</span>';
                            }
                            responseData += '</td><td>'+datavals[cdx]+'</td></tr>';
                        } else {
                            //console.log(childQuestions)
                        }
                    }
                }
                responseData += '</table>';
            } else if(question.type == 'text' || question.type == 'username') {
                if(typeof(datavals[key]) != 'undefined'){
                    responseData = datavals[key];
                } else {
                    responseData = 'N/A';
                }
            } else if (question.type == 'select one'){
                if(typeof question.children != 'undefined'){
                    for (child in question.children) {
                        if (datavals[key] == question.children[child].name) {
                            var selVal = question.children[child].label;
                            if(typeof selVal != 'string'){
                                selVal = selVal[language];
                            }
                        }
                    } 
                } else {
                        for(child in questionChoices){
                            for(var ttx in questionChoices[child]){
                                if(datavals[key] == questionChoices[child][ttx].name){
                                    var selVal = questionChoices[child][ttx].label;
                                    if(typeof selVal != 'string'){
                                        selVal = selVal[language];
                                    }
                                }
                            }            
                        }
                    }
                responseData += selVal;
                //console.log(question.children[child].name)
            } else if (question.type == 'image' || question.type == 'photo') {
                var src = _attachment_url(datavals[key], 'small');
                var href = _attachment_url(datavals[key], 'medium');
                var imgTag = $('<img/>').attr('src', src);
                responseData = '<a data-rel="fancybox-button" href="'+href+'" class="fancybox-button"><img alt="" src="'+src+'" class="img-responsive"></a>';
                //responseData = $('<div>').append($('<a>').attr('href', href).attr('target', '_blank').append(datavals[key])).html();
            } else if (question.type == 'audio' || question.type == 'video') {
                var href = _attachment_url(datavals[key], 'medium');
                responseData = $('<div>').append($('<a>').attr('href', href).attr('target', '_blank').append(datavals[key])).html();
            }
            //console.log(question.name)
            //console.log(responseData)
            keyValArr[key] = responseData;
            var trData = $('<tr class=""></tr>');
            trData.append(tdLabel);
            var tdData = $('<td data-key="' + key + '">'+responseData+'</td>');
            trData.append(tdData);
            tBody.append(trData);
        }
    }
    table.append(tHead);
    table.append(tBody);
    dataContainer.append(table);

    var bottomStatusNavRows = $('<div class="row"></div>');
    var bottomStatus = $(statusStr);
    bottomStatusNavRows.append(bottomStatus);

    var bottomPager = $(pagerStr);

    bottomStatusNavRows.append(bottomPager);
    //dataContainer.append(bottomStatusNavRows);

    $('select.language').change(function() {
        setLanguage(languages[parseInt($(this).val())]);
    });

    // set default language
    setLanguage(languages[0]);
}

function redirectToFirstId(context) {
    $.getJSON(mongoAPIUrl, {
            'limit': 1,
            'fields': '["_id"]',
            'sort': '{"_id": 1}'
        })
        .success(function(data) {
            if (data.length > 0)
                context.redirect('#/' + data[0]['_id']);
        })
        .error(function() {
            app.run('#/');
        })
}

function deleteData(context, data_id, id_string, username) {
    //TODO: show loader
    $.post(deleteAPIUrl, {
            'id': data_id
        })
        .success(function(data) {
            // update data count
            $.getJSON(mongoAPIUrl, {
                    'count': 1
                })
                .success(function(data) {
                    //todo: count num records before and num records after so we know our starting point
                    numRecords = data[0]["count"];
                    // redirect
                    context.redirect(redirect_route);
                })
        })
        .error(function() {
            alert(gettext('BAD REQUEST'));
        })
	$.ajax({
        url: '/delete-instance',
        type: "POST",
        data: {
            'data_id': data_id
        },
        success: function (response) {
            if (response == "data deleted") {
                window.location.href = '/usermodule/'+username+'/projects-views/'+id_string+'/';
            }
        }
    });
}

function loadData(context, query, canEdit) {

    //TODO: show loader
    $.getJSON(mongoAPIUrl, {
            'query': query,
            'limit': 1
        })
        .success(function(data) {
            reDraw(context, data[0], canEdit);

            //ADD EDIT AND BUTTON CHECK PERMISSION
            //updateButtons(data[0]);
            updateButtons(instance_id);

            //alert(data[0]['_id']);
            // check if we initialised the browsePos
            if (false) //TODO: find a way to increment browsePos client-side
            {
                updatePrevNextControls(data[0]);

                // update pos status text
                updatePosStatus();
            } else {
                $.getJSON(mongoAPIUrl, {
                        'query': '{"_id": {"$lt": ' + data[0]['_id'] + '}}',
                        'count': 1
                    })
                    .success(function(posData) {
                        browsePos = posData[0]["count"] + 1;
                        updatePrevNextControls(data[0]);
                    });
            }
        })
        .error(function() {
            alert(gettext("BAD REQUEST"));
        })
}

function setLanguage(language) {
    var idx = languages.indexOf(language);
    if (idx > -1) {
        $('span.language').hide();
        $(('span.language-' + idx)).show();
    }
}

function updatePosStatus() {
    var posText = positionTpl.replace('{pos}', browsePos);
    posText = posText.replace('{total}', numRecords);
    $('.record-pos').html(posText);
}

function updateButtons(data_id) {
	//console.log(data)
    //Make Edit Button visible and add link

    var editbutton = $('a.bind-edit');
    editbutton.removeClass('disabled');
    editbutton.attr('href', 'edit-data/' + data_id);


    //Make Delete Button visible and add link
    var deletebutton = $('#data a.btn-danger');
    deletebutton.removeClass('disabled');
    deletebutton.attr('href', '#del/' + data_id);
    $('#delete-modal a.btn-danger').attr('href', '#delete/' + data_id);

    // Add a note section
    $("#instance_id").val(data_id);
    $("#note").removeAttr("disabled");
}

function updatePrevNextControls(data) {
    // load next record
    $.getJSON(mongoAPIUrl, {
            'query': '{"_id": {"$gt": ' + data['_id'] + '}}',
            'limit': 1,
            'sort': '{"_id":1}',
            'fields': '["_id"]'
        })
        .success(function(nextData) {
            var nextButton = $('li.next');
            if (nextData.length > 0) {
                nextButton.removeClass('disabled');
                nextButton.children('a').attr('href', '#/' + nextData[0]['_id']);
            } else {
                nextButton.addClass('disabled');
                // make next url "the" current url
                nextButton.children('a').attr('href', '#/' + data['_id']);
            }
            // update pos status text
            updatePosStatus();
        });
    // load previous record
    $.getJSON(mongoAPIUrl, {
            'query': '{"_id": {"$lt": ' + data['_id'] + '}}',
            'limit': 1,
            'sort': '{"_id":-1}',
            'fields': '["_id"]'
        })
        .success(function(prevData) {
            var prevButton = $('li.prev');
            if (prevData.length > 0) {
                prevButton.removeClass('disabled');
                prevButton.children('a').attr('href', '#/' + prevData[0]['_id']);
            } else {
                prevButton.addClass('disabled');
                // make prev url "the" current url
                prevButton.children('a').attr('href', '#/' + data['_id']);
            }
            // update pos status text
            updatePosStatus();

            // if we haven't checked our position before
            if (browsePos) {
                // get num records before

            }
        });
}


function reDraw(context, data, canEdit) {
    if (data) {
        var cleanData = {};
        var cleanKey = '';
        for (var key in data) {
            var value = data[key];
            if (isArray(value) && typeof value[0] !== 'undefined') {
                for (var idx in value) {
                    var val_array = value[idx];
                    for (var sub_key in val_array) {
                        value_label = val_array[sub_key];
                        cleanKey = sub_key.replace(cleanRe, '_');
                    }
                }
            }
            cleanKey = key.replace(cleanRe, '_');

            if (cleanKey == '_submitted_by') {
                cleanData['username'] = data['_submitted_by'];
            } else {
                cleanData[cleanKey] = value;
            }
        }

        //console.log(cleanData)
        // check if table has been created, if not reCreate
        if ($('#data table').length == 0)
            createTable(canEdit,cleanData);

        $("#notes").show();

        var notes = data['_notes'],
            notesHTML = '<table class="table table-hover table-condensed">';
        if (notes.length > 0) {
            for (note in notes) {
                var n = notes[note];
                notesHTML += '<tr><td>' + n['note'] + '</td><td>' + n['date_modified'] + '</td><td>' +
                    '<button  onclick="editNote(this)" data-instance="' + n["instance"] + '" data-note="' + n['note'] + '" data-note-id="' + n['id'] + '" type="button" id="edit_note_' + n["id"] + '" class="btn btn-small btn-primary" >' + gettext("Edit note") + '</button>' +
                    '&nbsp;&nbsp;<i onclick="deleteNote(this)" data-instance="' + n["instance"] + '" data-note="' + n['note'] + '" data-note-id="' + n['id'] + '" class="remove-note icon-remove"></i>' +
                    '</td></tr>';
            }
            var nHTML = notesHTML + '</table>';
            $('#notes-section').html(nHTML);
        } else {
            $('#notes-section').empty();
        }

    } else {
        $('#data').empty();
        $('#data').html("<h3>" + gettext('The requested content was not found.') + "<h3>");
        $('#notes-section').empty();
        $("#notes").hide();
    }
}


function editNote(obj) {
    var note = $(obj).data('note'),
        note_id = $(obj).data('note-id');
    $('<input>').attr({
        type: 'hidden',
        id: 'note-id',
        name: 'id',
        value: note_id
    }).appendTo('#notesform');
    $("#notesform [name=note]").val(note);
}

function deleteNote(obj) {
    var note = $(obj).data('note');
    var note_id = $(obj).data('note-id');
    if (confirm("Are you sure you want to delete \"" + note + "\"?") == true) {
        $.ajax({
            url: "/api/v1/notes/" + note_id,
            type: "DELETE",
            statusCode: {
                404: function() {
                    alert("Note \"" + note + "\" not found or already deleted.");
                    app.refresh();
                }
            }
        }).done(function(data) {
            app.refresh();
        });
    }
}


function updateARStatus(data_id){
    var selected_status = $("#status_approve").val();
    var note=$("#note").val();
    //console.log(id_string);
    $.ajax({
        type: "POST",
        url: '/update-instance-status/',
        data: {'selected_status':selected_status,'note':note,'instance_id':data_id},
        success: function (result) {
        }
    });
}
