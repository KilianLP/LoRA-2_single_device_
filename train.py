#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 21:27:26 2024

@author: kilianpreuss
"""


from model import Transformer 
from Tokenizer import Tokenizer
from data_utils import DataSet,DataLoader
import torch
import torch.nn as nn
import torch.optim as optim
from datasets import load_dataset
from nltk.translate.bleu_score import sentence_bleu
import random
import numpy as np
from torch.cuda.amp import autocast, GradScaler
from torch.optim.lr_scheduler import LambdaLR
import wandb
import argparse 




parser = argparse.ArgumentParser(description="Model configuration arguments")


parser.add_argument("--dim", type=int, default=4096, help="Model dimension")
parser.add_argument("--n_layers", type=int, default=32, help="Number of layers")
parser.add_argument("--n_heads", type=int, default=32, help="Number of attention heads")
parser.add_argument("--n_kv_heads", type=int, default=8, help="Number of key-value heads")
parser.add_argument("--vocab_size", type=int, default=128256, help="Vocabulary size")
parser.add_argument("--multiple_of", type=int, default=256, help="Multiple of dimension for FFN")
parser.add_argument("--ffn_dim_multiplier", type=float, default=1.3, help="FFN dimension multiplier")
parser.add_argument("--norm_eps", type=float, default=1e-5, help="Epsilon for normalization layers")
parser.add_argument("--rope_theta", type=float, default=500000, help="Theta value for RoPE")


parser.add_argument("--n_translation_tokens", type=int, default=0, help="Number of translation tokens")
parser.add_argument("--max_batch_size", type=int, default=1, help="Maximum batch size")
parser.add_argument("--max_seq_len", type=int, default=2048, help="Maximum sequence length")
parser.add_argument("--alpha", type=float, default=2048, help="Alpha value for some algorithm")
parser.add_argument("--r", type=int, default=64, help="Reduction factor for some algorithm")
parser.add_argument("--mixed_precision", type=bool, default=False, help="Use mixed precision training")
parser.add_argument("--epochs", type=int, default=1, help="Number of training epochs")
parser.add_argument("--ignore_index", type=int, default=128255, help="Index to ignore during loss computation")
parser.add_argument("--lr", type=float, default=1e-6, help="Learning rate")
parser.add_argument("--n_expert", type=int, default=4, help="Number of experts")


parser.add_argument("--checkpoint_path", type=str, default="", help="Path to save checkpoints")
parser.add_argument("--checkpoint_epochs", type=int, default=1000000000, help="Checkpoint saving frequency in epochs")
parser.add_argument("--init_lr", type=float, default=1e-6, help="Initial learning rate for scheduler")
parser.add_argument("--max_lr", type=float, default=2e-4, help="Maximum learning rate for scheduler")
parser.add_argument("--warmup_epochs", type=int, default=600, help="Number of warmup epochs")


parser.add_argument("--gradient_accumulation", type=int, default=16, help="Number of gradient accumulation steps")
parser.add_argument("--model_parallel_size", type=int, default=1, help="model_parallel_size")
parser.add_argument("--ckpt_dir", type=str, default="/users2/local/kilian/checkpoints/Llama3.1-8B", help="ckpt_dir")



    


def bleu_evaluation(reference_texts, predicted_texts):
    bleu_scores = []
    
    for batch_idx in range(args.max_batch_size):
        reference_tokens = tokenizer.decode(reference_texts[batch_idx].tolist())
        reference_tokens = reference_tokens.replace("<|reserved_special_token_250|>", '').replace("<|end_of_text|>", '').replace(".", '')
        reference_words = [word for word in reference_tokens.split(" ") if word != '']
        
        
        valid_indices = [idx != args.ignore_index for idx in reference_texts[batch_idx].tolist()]
        predicted_tokens = predicted_texts[batch_idx][valid_indices]
        predicted_tokens = tokenizer.decode(predicted_tokens.tolist())
        predicted_tokens = predicted_tokens.replace("<|reserved_special_token_250|>", '').replace("<|end_of_text|>", '').replace(".", '')
        predicted_words = [word for word in predicted_tokens.split(" ") if word != '']
        
        
        bleu_scores.append(sentence_bleu([reference_words], predicted_words))
    
    return bleu_scores


def prepare_data_loaders_0(tokenizer):
    
    # Prepare data
    dataset = load_dataset("iwslt2017", "iwslt2017-en-it")
    
    train_data = dataset['train']
    valid_data = dataset['validation']
    
    
    # Train Data
    data_original = []
    data_target = []
    
    between_tokens = tokenizer.encode("The translation into Italian is:",bos = False, eos = False)
    
    for t in train_data:
        data_original.append(tokenizer.encode(t['translation']['en'],bos = True, eos = False))
        data_target.append(tokenizer.encode(t['translation']['it'],bos = False, eos = True))
    
    train_dataset = DataSet(data_original,data_target,between_tokens)
    train_dataloader = DataLoader(train_dataset,args.max_batch_size)
    
    # Eval Data
    data_original_valid = []
    data_target_valid = []
    
    for t in valid_data:
        data_original_valid.append(tokenizer.encode(t['translation']['en'],bos = True, eos = False))
        data_target_valid.append(tokenizer.encode(t['translation']['it'],bos = False, eos = True))
    
    
    valid_dataset = DataSet(data_original_valid,data_target_valid,between_tokens)
    valid_dataloader = DataLoader(valid_dataset,args.max_batch_size)
    
    return train_dataloader, valid_dataloader

def prepare_data_loaders_1(tokenizer):
    
    # Prepare data
    dataset = load_dataset("iwslt2017", "iwslt2017-en-de")
    
    train_data = dataset['train']
    valid_data = dataset['validation']
    
    
    # Train Data
    data_original = []
    data_target = []
    
    between_tokens = tokenizer.encode("The translation into German is:",bos = False, eos = False)
    
    for t in train_data:
        data_original.append(tokenizer.encode(t['translation']['en'],bos = True, eos = False))
        data_target.append(tokenizer.encode(t['translation']['de'],bos = False, eos = True))
    
    train_dataset = DataSet(data_original,data_target,between_tokens)
    train_dataloader = DataLoader(train_dataset,args.max_batch_size)
    
    # Eval Data
    data_original_valid = []
    data_target_valid = []
    
    for t in valid_data:
        data_original_valid.append(tokenizer.encode(t['translation']['en'],bos = True, eos = False))
        data_target_valid.append(tokenizer.encode(t['translation']['de'],bos = False, eos = True))
    
    
    valid_dataset = DataSet(data_original_valid,data_target_valid,between_tokens)
    valid_dataloader = DataLoader(valid_dataset,args.max_batch_size)
    
    return train_dataloader, valid_dataloader

def prepare_data_loaders_2(tokenizer):
    
    # Prepare data
    dataset = load_dataset("iwslt2017", "iwslt2017-it-nl")
    
    train_data = dataset['train']
    valid_data = dataset['validation']
    
    
    # Train Data
    data_original = []
    data_target = []
    
    between_tokens = tokenizer.encode("The translation into Dutch is:",bos = False, eos = False)
    
    for t in train_data:
        data_original.append(tokenizer.encode(t['translation']['it'],bos = True, eos = False))
        data_target.append(tokenizer.encode(t['translation']['nl'],bos = False, eos = True))
    
    train_dataset = DataSet(data_original,data_target,between_tokens)
    train_dataloader = DataLoader(train_dataset,args.max_batch_size)
    
    # Eval Data
    data_original_valid = []
    data_target_valid = []
    
    for t in valid_data:
        data_original_valid.append(tokenizer.encode(t['translation']['it'],bos = True, eos = False))
        data_target_valid.append(tokenizer.encode(t['translation']['nl'],bos = False, eos = True))
    
    
    valid_dataset = DataSet(data_original_valid,data_target_valid,between_tokens)
    valid_dataloader = DataLoader(valid_dataset,args.max_batch_size)
    
    return train_dataloader, valid_dataloader

def prepare_data_loaders_3(tokenizer):
    
    # Prepare data
    dataset = load_dataset("iwslt2017", "iwslt2017-it-ro")
    
    train_data = dataset['train']
    valid_data = dataset['validation']
    
    
    # Train Data
    data_original = []
    data_target = []
    
    between_tokens = tokenizer.encode("The translation into Romanian is:",bos = False, eos = False)
    
    for t in train_data:
        data_original.append(tokenizer.encode(t['translation']['it'],bos = True, eos = False))
        data_target.append(tokenizer.encode(t['translation']['ro'],bos = False, eos = True))
    
    train_dataset = DataSet(data_original,data_target,between_tokens)
    train_dataloader = DataLoader(train_dataset,args.max_batch_size)
    
    # Eval Data
    data_original_valid = []
    data_target_valid = []
    
    for t in valid_data:
        data_original_valid.append(tokenizer.encode(t['translation']['it'],bos = True, eos = False))
        data_target_valid.append(tokenizer.encode(t['translation']['ro'],bos = False, eos = True))
    
    
    valid_dataset = DataSet(data_original_valid,data_target_valid,between_tokens)
    valid_dataloader = DataLoader(valid_dataset,args.max_batch_size)
    
    return train_dataloader, valid_dataloader
    

def lr_scheduler(epoch,init_lr,max_lr,warmup_epochs):
    if epoch < warmup_epochs:
        return init_lr + (max_lr-init_lr)/warmup_epochs * epoch
    return max_lr
    




args = parser.parse_args()
    
random.seed(2)
torch.manual_seed(2)  
torch.cuda.manual_seed(2)
        


model = Transformer(args)
model = model.to(torch.bfloat16)
state_dict = torch.load("/home/maroc/.llama/checkpoints/Llama3.1-8B/consolidated.00.pth", map_location=torch.device('cpu'))
model.load_state_dict_lora(state_dict) 
model = model.to(torch.bfloat16)
model.prepare_lora_gradients()
model.to('cuda')

tokenizer = Tokenizer("/home/maroc/.llama/checkpoints/Llama3.1-8B/tokenizer.model")

train_dataloader_0, valid_dataloader_0 = prepare_data_loaders_0(tokenizer)
train_dataloader_1, valid_dataloader_1 = prepare_data_loaders_1(tokenizer)
train_dataloader_2, valid_dataloader_2 = prepare_data_loaders_2(tokenizer)
train_dataloader_3, valid_dataloader_3 = prepare_data_loaders_3(tokenizer)


# Training loop 
loss_fn = nn.CrossEntropyLoss(ignore_index=args.ignore_index)
optimizer = optim.Adam(model.parameters(), lr = args.init_lr)
scaler = GradScaler()
scheduler = LambdaLR(optimizer, lr_lambda=lambda batch_epoch: lr_scheduler(batch_epoch,args.init_lr,args.max_lr,args.warmup_epochs))

wandb.init(
    project="Llama_3_8B_en_it_^2",   
    config={              
        "r": args.r,
        "alpha": args.alpha,
        "learning_rate": args.max_lr,
    }
)


for e in range(args.epochs):
    
    blue_values_array = []
    for batch,target in valid_dataloader_2:
        
        model.eval()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch,0)
        prediction = torch.argmax(prediction_logits, dim = -1)
        
        bleu_values = bleu_evaluation(target,prediction)
        blue_values_array.append(np.mean(bleu_values))
        
    wandb.log({"Bleu it-nl": np.mean(blue_values_array)})
    
    blue_values_array = []
    for batch,target in valid_dataloader_3:
        
        model.eval()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch,1)
        prediction = torch.argmax(prediction_logits, dim = -1)
        
        bleu_values = bleu_evaluation(target,prediction)
        blue_values_array.append(np.mean(bleu_values))
        
    wandb.log({"Bleu it-ro": np.mean(blue_values_array)})
    
    train_dataloader_0_iter = iter(train_dataloader_0)
    train_dataloader_1_iter = iter(train_dataloader_1)
    train_dataloader_2_iter = iter(train_dataloader_2)
    train_dataloader_3_iter = iter(train_dataloader_3)
    
    
    for i in range(1,10**5):
        
        batch, target = next(train_dataloader_0_iter)
        model.train()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch,0)
        prediction_logits = prediction_logits.view(-1,args.vocab_size)
        target = target.view(-1)
        
        loss = loss_fn(prediction_logits,target)
        
        loss.backward()
        wandb.log({"train_loss_it": loss.item()})
        
        batch, target = next(train_dataloader_1_iter)
        model.train()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch,1)
        prediction_logits = prediction_logits.view(-1,args.vocab_size)
        target = target.view(-1)
        
        loss = loss_fn(prediction_logits,target)
        
        loss.backward()
        wandb.log({"train_loss_de": loss.item()})
        
        batch, target = next(train_dataloader_2_iter)
        model.train()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch,2)
        prediction_logits = prediction_logits.view(-1,args.vocab_size)
        target = target.view(-1)
        
        loss = loss_fn(prediction_logits,target)
        
        loss.backward()
        wandb.log({"train_loss_nl": loss.item()})
        
        batch, target = next(train_dataloader_3_iter)
        model.train()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch,3)
        prediction_logits = prediction_logits.view(-1,args.vocab_size)
        target = target.view(-1)
        
        loss = loss_fn(prediction_logits,target)
        
        loss.backward()
        wandb.log({"train_loss_ro": loss.item()})
              
                
        if i % args.gradient_accumulation == 0:
            optimizer.step()
            optimizer.zero_grad()
        
        scheduler.step()
        wandb.log({"lr": optimizer.param_groups[0]['lr']})
        wandb.log({"iter": i})
        
        if i % 1750 == 0:
            blue_values_array = []
            for batch,target in valid_dataloader_0:
                
                model.eval()
                batch = batch.to('cuda')
                target = target.to('cuda')
                
                prediction_logits = model(batch,0)
                prediction = torch.argmax(prediction_logits, dim = -1)
                
                bleu_values = bleu_evaluation(target,prediction)
                blue_values_array.append(np.mean(bleu_values))
                
            wandb.log({"Bleu en-it": np.mean(blue_values_array)})
            
            blue_values_array = []
            for batch,target in valid_dataloader_1:
                
                model.eval()
                batch = batch.to('cuda')
                target = target.to('cuda')
                
                prediction_logits = model(batch,1)
                prediction = torch.argmax(prediction_logits, dim = -1)
                
                bleu_values = bleu_evaluation(target,prediction)
                blue_values_array.append(np.mean(bleu_values))
                
            wandb.log({"Bleu en-de": np.mean(blue_values_array)})
            
            blue_values_array = []
            for batch,target in valid_dataloader_2:
                
                model.eval()
                batch = batch.to('cuda')
                target = target.to('cuda')
                
                prediction_logits = model(batch,2)
                prediction = torch.argmax(prediction_logits, dim = -1)
                
                bleu_values = bleu_evaluation(target,prediction)
                blue_values_array.append(np.mean(bleu_values))
                
            wandb.log({"Bleu it-nl": np.mean(blue_values_array)})
            
            blue_values_array = []
            for batch,target in valid_dataloader_3:
                
                model.eval()
                batch = batch.to('cuda')
                target = target.to('cuda')
                
                prediction_logits = model(batch,3)
                prediction = torch.argmax(prediction_logits, dim = -1)
                
                bleu_values = bleu_evaluation(target,prediction)
                blue_values_array.append(np.mean(bleu_values))
                
            wandb.log({"Bleu it-ro": np.mean(blue_values_array)})
        
    
    blue_values_array = []
    for batch,target in valid_dataloader_0:
        
        model.eval()
        batch = batch.to('cuda')
        target = target.to('cuda')
        
        prediction_logits = model(batch)
        prediction = torch.argmax(prediction_logits, dim = -1)
        
        bleu_values = bleu_evaluation(target,prediction)
        blue_values_array.append(np.mean(bleu_values))
        
    wandb.log({"Bleu": np.mean(blue_values_array)})
        
    model_state_dict = {key: value for key,value in model.state_dict().items() if "weight" not in key}
    torch.save(model_state_dict, args.checkpoint_path + f"r:{args.r}_alpha:{args.alpha}_learning_rate:{args.max_lr}")
            
            
    
    
    
   

