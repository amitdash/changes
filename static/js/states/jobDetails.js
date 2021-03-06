define([
  'app'
], function(app) {
  'use strict';

  var BUFFER_SIZE = 10000;

  return {
    url: "jobs/:job_id/",
    parent: 'build_details',
    templateUrl: 'partials/job-details.html',
    controller: function($scope, $http, $filter, projectData, buildData, jobData, stream, PageTitle, Pagination) {
      var logStreams = {};

      function getLogSourceEntrypoint(jobId, logSourceId) {
        return '/api/0/jobs/' + jobId + '/logs/' + logSourceId + '/';
      }

      function updateBuildLog(data) {
        // Angular isn't intelligent enough to optimize this.
        var $el = $('#log-' + data.source.id + ' > .build-log'),
            item, source_id = data.source.id,
            chars_to_remove, lines_to_remove,
            frag;

        if ($el.length === 0) {
          // logsource isnt available in viewpane
          return;
        }

        if (!logStreams[source_id]) {
          return;
        }

        item = logStreams[source_id];
        if (data.offset < item.nextOffset) {
          return;
        }

        item.nextOffset = data.offset + data.size;

        if (item.size > BUFFER_SIZE) {
          $el.empty();
        } else {
          // determine how much space we need to clear up to append data.size
          chars_to_remove = 0 - (BUFFER_SIZE - item.size - data.size);

          if (chars_to_remove > 0) {
            // determine the number of actual lines to remove
            lines_to_remove = item.text.substr(0, chars_to_remove).split('\n').length;

            // remove number of lines (accounted by <div>'s)
            $el.find('div').slice(0, lines_to_remove - 1).remove();
          }
        }

        frag = document.createDocumentFragment();

        // add each additional new line
        $.each(data.text.split('\n'), function(_, line){
          var div = document.createElement('div');
          div.className = 'line';
          div.innerHTML = line;
          frag.appendChild(div);
        });


        item.text = (item.text + data.text).substr(-BUFFER_SIZE);
        item.size = item.text.length;

        $el.append(frag);

        if ($el.is(':visible')) {
          var el = $el.get(0);
          el.scrollTop = Math.max(el.scrollHeight, el.clientHeight) - el.clientHeight;
        }
      }

      $scope.loadLogSource = function(logSource){
        logStreams[logSource.id] = {
          text: '',
          size: 0,
          nextOffset: 0
        };

        $http.get(getLogSourceEntrypoint($scope.job.id, logSource.id) + '?limit=' + BUFFER_SIZE)
          .success(function(data){
            $.each(data.chunks, function(_, chunk){
              updateBuildLog(chunk);
            });
          });
      };

      function updateJob(data){
        if (data.id !== $scope.job.id) {
          return;
        }

        $scope.$apply(function() {
          $scope.job = data;
        });
      }

      function getPageTitle(build, job) {
        if (build.number) {
          return 'Job #' + build.number + '.' + job.number +' - ' + projectData.name;
        }
        return 'Job ' + job.id + ' - ' + projectData.name;
      }

      function organizeLogSources(logSources) {
        var result = {};
        $.each(logSources, function(_, source){
          if (!source.step.phase) {
            // legacy, incompatible
            return;
          }
          var phaseId = source.step.phase.id;
          if (result[phaseId] === undefined) {
            result[phaseId] = [source];
          } else {
            result[phaseId].push(source);
          }
        });
        return result;
      }

      $scope.job = jobData.data;
      $scope.phases = jobData.data.phases;
      $scope.testFailures = jobData.data.testFailures;
      $scope.previousRuns = jobData.data.previousRuns;
      $scope.logSourcesByPhase = organizeLogSources(jobData.data.logs);

      PageTitle.set(getPageTitle(buildData, $scope.job));

      stream.addScopedChannels($scope, [
        'jobs:' + $scope.job.id,
        'logsources:' + $scope.job.id + ':*'
      ]);
      stream.addScopedSubscriber($scope, 'job.update', updateJob);
      stream.addScopedSubscriber($scope, 'buildlog.update', updateBuildLog);
    },
    resolve: {
      jobData: function($http, $stateParams) {
        return $http.get('/api/0/jobs/' + $stateParams.job_id + '/');
      }
    }
  };
});
