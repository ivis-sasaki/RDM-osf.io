'use strict';

var $ = require('jquery');
var nodeApiUrl = window.contextVars.node.urls.api;
var timestampCommon = require('./timestamp-common.js');


$(document).ready(function () {
    timestampCommon.initList();
});

$(function () {
    $('#btn-verify').on('click', function () {
        if ($('#btn-verify').attr('disabled') !== undefined || $('#btn-addtimestamp').attr('disabled') !== undefined) {
            return false;
        }
        timestampCommon.verify({
            urlVerify: 'json/',
            urlVerifyData: nodeApiUrl + 'timestamp/timestamp_error_data/',
            method: 'GET'
        });
    });

    $('#btn-addtimestamp').on('click', function () {
        if ($('#btn-verify').attr('disabled') !== undefined || $('#btn-addtimestamp').attr('disabled') !== undefined) {
            return false;
        }
        timestampCommon.add({
            url: nodeApiUrl + 'timestamp/add_timestamp/',
            method: 'GET'
        });
    });

    $('#btn-download').on('click', function () {
        timestampCommon.download();
    });

    $('#addTimestampAllCheck').on('change', function () {
        $('input[id=addTimestampCheck]').prop('checked', this.checked);
    });

    $('#timestamp_errors_spinner').hide();
});