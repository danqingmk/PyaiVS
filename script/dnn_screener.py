import torch
import os
import numpy as np
import pandas as pd
from script.dnn_torch_utils import Meter, MyDataset, EarlyStopping, MyDNN, collate_fn, set_random_seed
from hyperopt import fmin, tpe, hp, rand, STATUS_OK, Trials, partial
from torch.utils.data import DataLoader
from torch.nn import BCEWithLogitsLoss, MSELoss
import gc
import time
start_time = time.time()
import warnings
from sklearn import preprocessing
from script.splitdater import split_dataset
from script.feature_create import create_des
import torch
torch.set_num_threads(5)

def run_an_eval_epoch(model, data_loader, args):
    f = open(args['output'],'w+')
    f.write('cano_smiles,pred_prop\n')
    count = 0
    model.eval()
    # eval_metric = Meter()
    with torch.no_grad():
        for batch_id, batch_data in enumerate(data_loader):
            eval_metric = Meter()
            Xs, Ys, masks = batch_data
            Xs, Ys, masks = Xs.to(args['device']), Ys.to(args['device']), masks.to(args['device'])
            outputs = model(Xs)
            outputs.cpu()
            Ys.cpu()
            masks.cpu()
#            torch.cuda.empty_cache()

            eval_metric.update(outputs, Ys, torch.tensor([count]))
            roc_score = eval_metric.compute_metric('pred')
            smiles = args['data'][args['smiles_col']].tolist()[int(Ys[0])]
            write_check = 0
            for score in roc_score:
                if score>= args['prop']:
                    write_check =1
                    break
            if write_check ==1:

                f.write('{},{}\n'.format(smiles, ','.join([str(round(float(score),3)) for score in roc_score])))
            count += 1
            torch.cuda.empty_cache()
        f.close()
def screen(file='', sep=',', models=None,prop=0.5, smiles_col='Smiles',out_dir=None,tasks=1):

    my_df = pd.read_csv(file, engine='python', sep=sep)

    device = torch.device("cpu")
    args = {'device': device, 'metric': 'roc_auc','prop':prop,'data':my_df,'smiles_col':smiles_col,'tasks':tasks}
    outputs = os.path.join(out_dir,
                           file.split('/')[-1].replace('.csv', '_screen_{}_{}.csv'.format(args['prop'], 'DNN')))
    if os.path.exists(outputs):
        print(outputs, 'has done')
    else:
        args['output'] = outputs
        FP_type = models.split('/')[-1].split('_')[1]
        model_dir = out_dir.replace(out_dir.split('/')[-1],'model_save')
        print(smiles_col)
        data_x, data_y = create_des(my_df[smiles_col], list(range(len(my_df))), FP_type=FP_type, model_dir=model_dir)

        dataset = MyDataset(data_x, data_y)
        loader = DataLoader(dataset,  collate_fn=collate_fn)
        inputs = data_x.shape[1]
        hideen_unit = (eval(models.split('/')[-1].split('_')[5]),
                       eval(models.split('/')[-1].split('_')[6])
                       ,eval(models.split('/')[-1].split('_')[7]))

        dropout = eval(models.split('/')[-1].split('_')[4])
        best_model = MyDNN(inputs=inputs, hideen_units=hideen_unit, outputs=tasks,
                           dp_ratio=dropout, reg=False)
        best_model.load_state_dict(torch.load(models, map_location=device)['model_state_dict'])
        best_model.to(device)
        run_an_eval_epoch(best_model, loader, args)
#
# screen(models ='/data/jianping/bokey/OCAICM/dataset/chembl31/model_save/DNN/cla_ECFP4_cluster_dataset_0.0016_64_512_128_0.0047_early_stop.pth',
#        file='/data/jianping/bokey/OCAICM/dataset/chembl31/model_save/BACE_screen_0.5_DNN.csv',prop = 0.5,sep = ',',
#        out_dir='/data/jianping/bokey/OCAICM/dataset/chembl31/model_save',smiles_col='cano_smiles',tasks=1)
