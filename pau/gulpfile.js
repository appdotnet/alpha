/* global require: true */
'use strict';

var gulp = require('gulp');

var sass = require('gulp-ruby-sass');
var uglify = require('gulp-uglify');
var concat = require('gulp-concat');

var paths = {
    css: 'static/css/pau.scss',
    js: [
        'static/js/deps/modernizr/modernizr.js',
        'static/js/deps/bootstrap/bootstrap-collapse.js',
        'static/js/deps/bootstrap/bootstrap-dropdown.js',
        'static/js/deps/bootstrap/bootstrap-modal.js',
        'static/js/deps/cookie/jquery.cookie.js',
        'static/js/deps/placeholder/jquery.placeholder.js',
        'static/js/deps/twitter-typeahead/typeahead.js',
        'static/js/deps/json/json2.js',
        'static/js/deps/pubsub/pubsub.js',
        'static/js/deps/underscore/underscore.js',
        'static/js/deps/pjax/jquery.pjax.js',
        'static/js/deps/imagesloaded/jquery.imagesloaded.js',
        'static/js/core/csrf.js',
        'static/js/core/init.js',
        'static/js/core/feature_detection.js',
        'static/js/core/module.js',
        'static/js/modules/appdotnet_api.js',
        'static/js/modules/utils.js',
        'static/js/modules/dialogs.js',
        'static/js/modules/event_tracking.js',
        'static/js/modules/file_uploads.js',
        'static/js/modules/autocomplete.js',
        'static/js/modules/pau.js',
        'static/js/modules/message_create.js',
        'static/js/modules/stream_view.js',
        'static/js/modules/follow.js',
        'static/js/modules/photo.js',
    ]
};

gulp.task('javascript', function() {

  return gulp.src(paths.js)
    .pipe(uglify())
    .pipe(concat('pau.js'))
    .pipe(gulp.dest('static/build_output/js/'));
});

gulp.task('css', function() {

  return gulp.src(paths.css)
    .pipe(sass())
    .pipe(gulp.dest('static/build_output/css/'));
});

// Rerun the task when a file changes
gulp.task('watch', function() {
  gulp.watch(paths.js, ['javascript']);
  gulp.watch(['static/css/*.scss'], ['css']);
});

// The default task (called when you run `gulp` from cli)
gulp.task('default', ['javascript', 'css', 'watch']);
