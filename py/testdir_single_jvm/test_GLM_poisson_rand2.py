import unittest
import random, sys, time
sys.path.extend(['.','..','py'])

import h2o, h2o_cmd, h2o_glm, h2o_hosts

def define_params():
    paramDict = {
        'x': [0,1,15,33,34],
        'family': ['poisson'],
        'n_folds': [2,3,4,9],
        'thresholds': [0.1, 0.5, 0.7, 0.9],
        'lambda': [1e-8, 1e-4],
        'alpha': [0,0.5,0.75],
        # don't use defaults? they have issues?
        'beta_epsilon': [0.001, 0.0001],
        # case_mode not used for poisson?
        # inverse and log causing problems
        # 'link': [None, 'logit','identity', 'log', 'inverse'],
        # don't use defaults? they have issues?
        'max_iter': [5, 10, 19, 31],
        'weight': [None, 1, 2, 4],
        }
    return paramDict

class Basic(unittest.TestCase):
    def tearDown(self):
        h2o.check_sandbox_for_errors()

    @classmethod
    def setUpClass(cls):
        global localhost
        localhost = h2o.decide_if_localhost()
        if (localhost):
            h2o.build_cloud(node_count=1)
        else:
            h2o_hosts.build_cloud_with_hosts(node_count=1)

    @classmethod
    def tearDownClass(cls):
        h2o.tear_down_cloud()

    def test_loop_random_param_covtype(self):
        csvPathname = h2o.find_dataset('UCI/UCI-large/covtype/covtype.data')
        parseKey = h2o_cmd.parseFile(csvPathname=csvPathname)

        # for determinism, I guess we should spit out the seed?
        # random.seed(SEED)
        SEED = random.randint(0, sys.maxint)
        # if you have to force to redo a test
        # SEED = 
        random.seed(SEED)
        paramDict = define_params()
        print "\nUsing random seed:", SEED
        for trial in range(20):
            # params is mutable. This is default.
            # FIX! does it never end if we don't have alpha specified?
            params = {
                'y': 54, 
                'n_folds': 3, 
                'family': "poisson", 
                'alpha': 0.5, 
                'lambda': 1e-4, 
                'beta_epsilon': 0.001, 
                'max_iter': 30
                }

            colX = h2o_glm.pickRandGlmParams(paramDict, params)
            kwargs = params.copy()

            # make timeout bigger with xvals
            timeoutSecs = 60 + (kwargs['n_folds']*20)
            # or double the 4 seconds per iteration (max_iter+1 worst case?)
            timeoutSecs = max(timeoutSecs, (8 * (kwargs['max_iter']+1)))

            start = time.time()
            glm = h2o_cmd.runGLMOnly(timeoutSecs=timeoutSecs, parseKey=parseKey, **kwargs)
            print "glm end on ", csvPathname, 'took', time.time() - start, 'seconds'

            h2o_glm.simpleCheckGLM(self, glm, None, **kwargs)
            print "Trial #", trial, "completed\n"


if __name__ == '__main__':
    h2o.unit_main()
