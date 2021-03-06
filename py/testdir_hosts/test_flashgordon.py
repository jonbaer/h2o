import unittest, sys, random, time
sys.path.extend(['.','..','py'])
import h2o, h2o_cmd, h2o_browse as h2b, h2o_import as h2i, h2o_hosts
import h2o_jobs
import logging

class Basic(unittest.TestCase):
    def tearDown(self):
        h2o.check_sandbox_for_errors()

    @classmethod
    def setUpClass(cls):
        print "Will build clouds with incrementing heap sizes and import folder/parse"

    @classmethod
    def tearDownClass(cls):
        # the node state is gone when we tear down the cloud, so pass the ignore here also.
        h2o.tear_down_cloud(sandbox_ignore_errors=True)

    def test_flashgordon(self):
        # typical size of the michal files
        avgMichalSize = 116561140
        avgSynSize = 4020000
        csvFilenameList = [
            ("100.dat.gz", "dat_1", 1 * avgSynSize, 700),
            ("11[0-9].dat.gz", "dat_10", 10 * avgSynSize, 700),
            ("1[32][0-9].dat.gz", "dat_20", 20 * avgSynSize, 800),
            ("1[5-9][0-9].dat.gz", "dat_50", 50 * avgSynSize, 900),
            # ("1[0-9][0-9].dat.gz", "dat_100", 100 * avgSynSize, 1200),
        ]

        print "Using the -.gz files from s3"
        # want just s3n://home-0xdiag-datasets/manyfiles-nflx-gz/file_1.dat.gz
    
        USE_S3 = False
        noPoll = True
        benchmarkLogging = ['cpu','disk']
        bucket = "home-0xdiag-datasets"
        if USE_S3:
            URI = "s3://flashgordon"
            protocol = "s3"
        else:
            URI = "s3n://flashgordon"
            protocol = "s3n/hdfs"

        # split out the pattern match and the filename used for the hex
        trialMax = 1
        # use i to forward reference in the list, so we can do multiple outstanding parses below
        for i, (csvFilepattern, csvFilename, totalBytes, timeoutSecs) in enumerate(csvFilenameList):
            ## for tryHeap in [54, 28]:
            for tryHeap in [54]:
                
                print "\n", tryHeap,"GB heap, 1 jvm per host, import", protocol, "then parse"
                h2o_hosts.build_cloud_with_hosts(node_count=1, java_heap_GB=tryHeap,
                    enable_benchmark_log=True, timeoutSecs=120, retryDelaySecs=10,
                    # all hdfs info is done thru the hdfs_config michal's ec2 config sets up?
                    # this is for our amazon ec hdfs
                    # see https://github.com/0xdata/h2o/wiki/H2O-and-s3n
                    hdfs_name_node='10.78.14.235:9000',
                    hdfs_version='0.20.2')

                # don't raise exception if we find something bad in h2o stdout/stderr?
                h2o.nodes[0].sandbox_ignore_errors = True

                for trial in range(trialMax):
                    # since we delete the key, we have to re-import every iteration, to get it again
                    # s3n URI thru HDFS is not typical.
                    if USE_S3:
                        importResult = h2o.nodes[0].import_s3(bucket)
                    else:
                        importResult = h2o.nodes[0].import_hdfs(URI)

                    s3nFullList = importResult['succeeded']
                    for k in s3nFullList:
                        key = k['key']
                        # just print the first tile
                        # if 'nflx' in key and 'file_1.dat.gz' in key: 
                        if csvFilepattern in key:
                            # should be s3n://home-0xdiag-datasets/manyfiles-nflx-gz/file_1.dat.gz
                            print "example file we'll use:", key
                            break
                        else:
                            ### print key
                            pass

                    ### print "s3nFullList:", h2o.dump_json(s3nFullList)
                    # error if none? 
                    self.assertGreater(len(s3nFullList),8,"Didn't see more than 8 files in s3n?")

                    s3nKey = URI + "/" + csvFilepattern
                    key2 = csvFilename + "_" + str(trial) + ".hex"
                    print "Loading", protocol, "key:", s3nKey, "to", key2
                    start = time.time()
                    parseKey = h2o.nodes[0].parse(s3nKey, key2,
                        timeoutSecs=timeoutSecs, retryDelaySecs=10, pollTimeoutSecs=60,
                        noPoll=noPoll,
                        benchmarkLogging=benchmarkLogging)

                    if noPoll:
                        time.sleep(1)
                        h2o.check_sandbox_for_errors()
                        (csvFilepattern, csvFilename, totalBytes2, timeoutSecs) = csvFilenameList[i+1]
                        s3nKey = URI + "/" + csvFilepattern
                        key2 = csvFilename + "_" + str(trial) + ".hex"
                        print "Loading", protocol, "key:", s3nKey, "to", key2
                        parse2Key = h2o.nodes[0].parse(s3nKey, key2,
                            timeoutSecs=timeoutSecs, retryDelaySecs=10, pollTimeoutSecs=60,
                            noPoll=noPoll,
                            benchmarkLogging=benchmarkLogging)

                        time.sleep(1)
                        h2o.check_sandbox_for_errors()
                        (csvFilepattern, csvFilename, totalBytes3, timeoutSecs) = csvFilenameList[i+2]
                        s3nKey = URI + "/" + csvFilepattern
                        key2 = csvFilename + "_" + str(trial) + ".hex"
                        print "Loading", protocol, "key:", s3nKey, "to", key2
                        parse3Key = h2o.nodes[0].parse(s3nKey, key2,
                            timeoutSecs=timeoutSecs, retryDelaySecs=10, pollTimeoutSecs=60,
                            noPoll=noPoll,
                            benchmarkLogging=benchmarkLogging)

                    elapsed = time.time() - start
                    print s3nKey, 'parse time:', parseKey['response']['time']
                    print "parse result:", parseKey['destination_key']
                    print "Parse #", trial, "completed in", "%6.2f" % elapsed, "seconds.", \
                        "%d pct. of timeout" % ((elapsed*100)/timeoutSecs)

                    # print stats on all three if noPoll
                    if noPoll:
                        # does it take a little while to show up in Jobs, from where we issued the parse?
                        time.sleep(2)
                        # FIX! use the last (biggest?) timeoutSecs? maybe should increase since parallel
                        h2o_jobs.pollWaitJobs(pattern=csvFilename, 
                            timeoutSecs=timeoutSecs, benchmarkLogging=benchmarkLogging)
                        # for getting the MB/sec closer to 'right'
                        totalBytes += totalBytes2 + totalBytes3
                        elapsed = time.time() - start
                        h2o.check_sandbox_for_errors()

                    if totalBytes is not None:
                        fileMBS = (totalBytes/1e6)/elapsed
                        print "\nMB/sec (before uncompress)", "%6.2f" % fileMBS
                        h2o.cloudPerfH2O.message('{:d} jvms, {:d}GB heap, {:s} {:s} {:6.2f} MB/sec for {:6.2f} secs'.format(
                            len(h2o.nodes), tryHeap, csvFilepattern, csvFilename, fileMBS, elapsed))

                    # BUG here?
                    if not noPoll:
                        # We should be able to see the parse result?
                        inspect = h2o_cmd.runInspect(key=parseKey['destination_key'])

                    print "Deleting key in H2O so we get it from S3 (if ec2) or nfs again.", \
                          "Otherwise it would just parse the cached key."

                    storeView = h2o.nodes[0].store_view()
                    ### print "storeView:", h2o.dump_json(storeView)
                    # "key": "s3n://home-0xdiag-datasets/manyfiles-nflx-gz/file_84.dat.gz"
                    # have to do the pattern match ourself, to figure out what keys to delete
                    # we're deleting the keys in the initial import. We leave the keys we created
                    # by the parse. We use unique dest keys for those, so no worries.
                    # Leaving them is good because things fill up! (spill)
                    for k in s3nFullList:
                        deleteKey = k['key']
                        if csvFilename in deleteKey and not ".hex" in key:      
                            pass
                            # h2o removes key after parse now
                            ### print "Removing", deleteKey
                            ### removeKeyResult = h2o.nodes[0].remove_key(key=deleteKey)
                            ### print "removeKeyResult:", h2o.dump_json(removeKeyResult)

                h2o.tear_down_cloud()
                # sticky ports? wait a bit.
                time.sleep(120)

if __name__ == '__main__':
    h2o.unit_main()
