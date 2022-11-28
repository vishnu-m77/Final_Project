# imports
import torch
import numpy as np
from torch import nn
import torch.functional as func
import pandas as pd
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
class utils():
    def __init__(self) -> None:
        pass

    def mask_inputs(nn_input, layer):
        """
        May need to modify multiplications depending on dimensions
        """
        if (layer % 2 != 0):
            nn_masked_mat = torch.from_numpy(np.array([[1.,0.,0.,0.],[0.,0.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])).to(torch.float32)
            var_mask = torch.tensor([1.,0.]).to(torch.float32)
            mask_prime = torch.tensor([0.,1.]).to(torch.float32)
            # #nn_masked_input = nn_input*[:,[1,0,1,1]]
            # nn_masked_input = torch.matmul(nn_input, nn_mask_mat)
            # #var_masked = var*[1,0]
            # var_masked = torch.matmul(var, var_mask_mat)
            # #var_masked_prime = var*[0,1]
            # var_masked_prime = torch.matmul(var, torch.eye(2)-var_mask_mat)
        else:
            nn_masked_mat = torch.from_numpy(np.array([[0.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])).to(torch.float32)
            var_mask = torch.tensor([0.,1.]).to(torch.float32)
            mask_prime = torch.tensor([1.,0.]).to(torch.float32)
            # nn_masked_input = torch.matmul(nn_input, nn_mask_mat)
            # var_masked = torch.matmul(var, var_mask_mat)
            # var_masked_prime = torch.matmul(var, torch.eye(2)-var_mask_mat)
        return nn_masked_mat, var_mask,mask_prime # torch.eye(2)-var_mask_mat is mask_prime


class Net(nn.Module):
    def __init__(self, hidden_units=10):
        super(Net, self).__init__()
        self.input_units = 4
        self.hidden_units = hidden_units # need to make it a hyper-parameter
        self.output_units = 2

        self.fc1 = nn.Linear(self.input_units, self.hidden_units)
        self.fc2 = nn.Linear(self.hidden_units, self.output_units)

    def forward(self, x):
        h = torch.tanh(self.fc1(x))
        #print("x in FORQARD IS {0}".format(x))
        y = self.fc2(h)
        return y


class RealNVPtransforms(Net):

    def __init__(self):
        super(RealNVPtransforms, self).__init__()
        self.s = Net(hidden_units=10)
        self.t = Net(hidden_units=10)

    def forward_transform(self, layer, x, y):
        """
        Forward transform of flux data y = [flux,flux_err] to latent z conditioned on x = [time_stamp, passband]
        """
        nn_input = torch.cat((y,x),dim=1)
        nn_mask_mat, var_mask, mask_prime = utils.mask_inputs(nn_input, layer)
        nn_masked_input = torch.matmul(nn_input, nn_mask_mat)
        s_forward = self.s.forward(nn_masked_input)
        t_forward = self.t.forward(nn_masked_input)
        #print("nn_mask_mat is {0}".format(nn_masked_input))
        #print("mask_prime is {0}".format(mask_prime))
        #print("mask is {0}".format(var_mask))
        #print("y*var_mask is {0}".format((y*torch.exp(s_forward)+t_forward)*mask_prime))
        #if (layer%2==0):
        y_forward = (y*torch.exp(s_forward)+t_forward)*mask_prime+y*var_mask
        #print("s_forward is {0}".format(s_forward))
        #y_forward = y_masked_prime*(torch.exp(s_forward)+self.t.forward(nn_masked_input))+y_masked
        #y_forward = y_masked_prime*(torch.exp(s_forward))+mask_prime*self.t.forward(nn_masked_input)+y_masked # masking fixed :: can be improved
        #y_forward = (y*torch.exp(s_forward)+t_forward)*mask_prime+y_masked
        """
        need to compute determinant
        """
        log_det = torch.sum(s_forward*mask_prime, dim=1)
        #print("log det is: {0}".format(log_det))
        #print("det_comp is : {0}".format(det_comp))
        return y_forward, log_det # use this s_forard to compute the determinant

    def inverse_transform(self, layer, z, x):
        """
        UPDATE: inverse transformed edited according to new masking but needs to be VERIFIED !!!
        """
        """
        Inverse transform of latent z to flux data y = [flux,flux_err] conditioned on x = [time_stamp, passband]
        """
        nn_input = torch.cat((z,x), dim=0)
        nn_mask_mat, var_mask, mask_prime = utils.mask_inputs(nn_input, layer)
        #x_backward = (z-self.t.forward(nn_masked_input))*torch.exp(-self.s.forward(nn_masked_input))*mask_prime+z_masked
        nn_masked_input = torch.matmul(nn_input, nn_mask_mat)
        s_forward = self.s.forward(nn_masked_input)
        t_forward = self.t.forward(nn_masked_input)
        z_backward = (z - t_forward)*torch.exp(-s_forward)*mask_prime+z*var_mask
        return z_backward

class NormalizingFlowsBase(RealNVPtransforms):
    def __init__(self, num_layers):
        super(NormalizingFlowsBase, self).__init__()
        self.num_layers = num_layers
        self.prior = torch.distributions.MultivariateNormal(torch.zeros(2), torch.eye(2))

    def full_forward_transform(self, x, y):
        log_likelihood = 0
        for layer in range(self.num_layers):
            y, det = self.forward_transform(layer, x, y)
            log_likelihood = log_likelihood + det
        prior_stuff = self.prior.log_prob(y)
        #print("prior gives: {0}".format(prior_stuff))
        log_likelihood = log_likelihood + prior_stuff
        z = y
        #print("mean is log_likelihood.mean() is {0}".format(log_likelihood.mean()))
        return z, log_likelihood.mean()
    
    # def compute_transform_determinant(self, s_list):


    def full_backward_transform(self, z, x):
        for layer in range(self.num_layers):
            z = self.inverse_transform(layer, z, x)
            #print("y in layer {0} is {1}".format(layer, z))
        y = z
        return y
    
    def sample_data(self, x):
        z = torch.from_numpy(np.asarray(self.prior.sample()))
 #       print(z)
        y = self.full_backward_transform(z,x)
        #print("final flux is {0}".format(y[0])) # flux
        return y



if __name__ == '__main__':
    """
    # run normalizing flow directly for testng
    """
    data_dir = 'data/ANTARES_NEW.csv'
    df = pd.read_csv(data_dir)
    #print(df['object_id']=='ZTF21abwxaht')
    object_name = 'ZTF20aahbamv'
    df_obj = df.loc[df['object_id']==object_name]
    timestamp = np.asarray(df_obj['mjd'])
    passbands = np.asarray(df_obj['passband'])
    wavelength_arr = []
    for pb in passbands:
        if pb==0:
            wavelength_arr.append(np.log10(3751.36))
        elif pb==1:
            wavelength_arr.append(np.log10(4741.64))
        else:
            print("Passband invalid")
    flux = np.asarray(df_obj['flux'])
    flux_err = np.asarray(df_obj['flux_err'])

    X = []
    y = []
    for i in range(len(passbands)):
        X.append(np.array([timestamp[i], wavelength_arr[i]]))
        y.append(np.array([flux[i], flux_err[i]]))
    X = torch.from_numpy(np.array(X)).to(torch.float32)
    y = torch.from_numpy(np.array(y)).to(torch.float32)
    #print(df[0])
    """
    # RealNVP = RealNVPtransforms()
    # out= RealNVP.forward_transform(0,X, y)
    # #print(out)
    # NF = NormalizingFlowsBase(num_layers=8)
    # NF.full_forward_transform(X, y)
    """

# rewrite training loop
    NF = NormalizingFlowsBase(num_layers=8)
    optimizer = torch.optim.Adam(NF.parameters(), lr=0.0001)
    num_epochs = 8000
    X = StandardScaler().fit_transform(X)
    X = torch.from_numpy(X).to(torch.float32)
    for epoch in range(num_epochs):
        _ , loss = NF.full_forward_transform(X,y)
        loss = -loss
        optimizer.zero_grad()
        loss.backward()
        optimizer.step() 
        if ((epoch+1) % 200 ==0):
            print("Epoch: {0} and Loss: {1}".format(epoch+1, loss))
    
    pred_flux = []
    orig_flux = []
    #for i in range(len(flux)):
    i = 140
    for i in range(len(flux)):
        if (i+1)%5==0:
            inp = X[i] # 119, 160 works
            num_samples = 1500
            flux_approx = []
            for j in range(num_samples):
                flux_approx.append(NF.sample_data(inp)[0])
            mean_flux = sum(flux_approx)/len(flux_approx)
            pred_flux.append(mean_flux)
            orig_flux.append(flux[i])
            print("Original flux is {0} and predicted flux is {1} for flux {2}".format(flux[i],mean_flux,i+1))
    original_flux = orig_flux

"""

    NF = NormalizingFlowsBase(num_layers=8)
    # out, log_likelihood = NF.full_forward_transform(X,y)
    optimizer = torch.optim.Adam(NF.parameters(), lr=0.0001)
    # print("S FORWARDS")
    #print("log_like is {0}".format(log_likelihood))
    num_epochs = 5000
    print("prec x is {0}".format(X))
    #X = np.concatenate((np.asarray(timestamp).reshape(-1, 1), np.asarray(wavelength_arr).reshape(-1, 1)), axis=1)
    #print("concat x is {0}".format(X))
    X = StandardScaler().fit_transform(X)
    print("SS on orig x is {0}".format(X))
    X = torch.from_numpy(X).to(torch.float32)
    for epoch in range(num_epochs):
        _ , loss = NF.full_forward_transform(X,y)
        loss = -loss
        optimizer.zero_grad()
        loss.backward()
        optimizer.step() 
        if ((epoch+1) % 50 ==0):
            print("Epoch: {0} and Loss: {1}".format(epoch+1, loss))
        # if loss<=0.05:
        #     break
    #inp = torch.from_numpy(np.asarray([X[0]])).to(torch.float32)
    inp = X[1]
    print(inp)
    num_samples = 1000
    flux_approx = []
    for i in range(num_samples):
        flux_approx.append(NF.sample_data(inp)[0])
    mean_flux = sum(flux_approx)/len(flux_approx)
    #num_accepted_samples = num_samples
    # for i in range(num_samples):
    #     if abs(flux_approx[i])>10:
    #         flux_approx[i] = 0
    #         num_accepted_samples = num_accepted_samples - 1
    # mean_flux = sum(flux_approx)/num_accepted_samples
    print("mean_flux is {0}".format(mean_flux))
"""
    