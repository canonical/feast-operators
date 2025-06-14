Get started 
============

This guide describes how to deploy Charmed Feast along with `Charmed Kubeflow (CKF) <https://charmed-kubeflow.io/docs>`_, 
including requirements, environment setup, and deployment steps using `Terraform <https://developer.hashicorp.com/terraform>`_. 

.. note::
   This content is intended for system administrators and MLOps engineers.

CKF provides a simple, out-of-the-box way to deploy Kubeflow.
Charmed Feast bundle adds a fully integrated feature store to that deployment. 

Requirements
------------

- Ubuntu 22.04 or later.
- A host machine with at least:

  - 4-core CPU processor.
  - 32 GB RAM.
  - 50 GB available disk space.

Install and configure dependencies
----------------------------------

CKF relies on:

- Kubernetes (K8s): This tutorial uses `MicroK8s <https://microk8s.io/docs>`_, a zero-ops Kubernetes distribution.
- `Juju <https://juju.is/>`_: A software orchestration engine used to deploy and manage Charmed Feast and CKF.

Install MicroK8s
^^^^^^^^^^^^^^^^

Install MicroK8s using `Snapcraft <https://snapcraft.io/>`_:

.. code-block:: bash

   sudo snap install microk8s --channel=1.32/stable --classic

Add your user to the MicroK8s group:

.. code-block:: bash

   sudo usermod -a -G microk8s $USER

Apply the new group permissions:

.. code-block:: bash

   newgrp microk8s

See `Get started with MicroK8s <https://microk8s.io/docs/getting-started>`_ for more details.

Enable MicroK8s addons:

.. code-block:: bash

   sudo microk8s enable dns hostpath-storage metallb:10.64.140.43-10.64.140.49 rbac

Check the status:

.. code-block:: bash

   microk8s status

Install Juju
^^^^^^^^^^^^^

Install Juju using Snapcraft:

.. code-block:: bash

   sudo snap install juju --channel=3.6/stable

Ensure the required local directory exists:

.. code-block:: bash

   mkdir -p ~/.local/share

See `Get started with Juju <https://documentation.ubuntu.com/juju/3.6/tutorial/>`_ for more details.

Configure Juju
^^^^^^^^^^^^^^^

Add your MicroK8s cluster to Juju:

.. code-block:: bash

   microk8s config | juju add-k8s my-k8s --client

Bootstrap a Juju controller:

.. code-block:: bash

   juju bootstrap my-k8s uk8sx

Deploy Charmed Feast along with CKF
------------------------------------

You can deploy Charmed Feast together with CKF using Terraform. 

Start by cloning the solution repository:

.. code-block:: bash

   git clone https://github.com/canonical/charmed-kubeflow-solutions.git
   cd charmed-kubeflow-solutions/modules/kubeflow-feast/

Install Terraform:

.. code-block:: bash

   sudo snap install terraform --classic

Initialise and apply the deployment:

.. code-block:: bash

   terraform init
   terraform apply -auto-approve

.. note:: 
   This process may take several minutes. 

Once completed, both Charmed Feast and CKF will be fully deployed and integrated.

Check component status
------------------------

After the deployment, the bundle components need some time to initialise and establish communication with each other.

.. note::
   This process may take up to 20 minutes.

Check the status of the components as follows:

.. code-block:: bash

   juju switch kubeflow
   juju status

Use the watch option to continuously track their status:

.. code-block:: bash

   juju status --watch 5s

You should expect an output like this:

.. code-block:: none

   Model     Controller       Cloud/Region         Version  SLA          Timestamp
   kubeflow  uk8sx            my-k8s/localhost     3.6.4    unsupported  16:12:02Z

   App                   Version         Status  Scale  Charm                Channel      Rev  Address         Exposed  Message
   feast-integrator                                  active       1  feast-integrator         latest/edge        72  10.152.183.67   no       
   feast-offline-store      14.15                    active       1  postgresql-k8s           14/stable         495  10.152.183.66   no       
   feast-online-store       14.15                    active       1  postgresql-k8s           14/stable         495  10.152.183.236  no       
   feast-registry           14.15                    active       1  postgresql-k8s           14/stable         495  10.152.183.252  no       
   feast-ui                                          active       1  feast-ui                 latest/edge        42  10.152.183.47   no       

   Unit                  Workload  Agent  Address      Ports  Message
   feast-integrator/0*         active    idle   10.1.202.83                  
   feast-offline-store/0*      active    idle   10.1.202.122                 Primary
   feast-online-store/0*       active    idle   10.1.202.102                 Primary
   feast-registry/0*           active    idle   10.1.202.123                 Primary
   feast-ui/0*                 active    idle   10.1.202.121         

CKF is ready when all the applications and units are in ``active`` status. 
During the configuration process, some components may temporarily show a ``blocked`` or ``error`` state, which is expected and usually resolves automatically.

Access your deployment
----------------------

You can interact with CKF using a web dashboard accessible via an IP address.

Set the dashboard login credentials:

.. code-block:: bash

   juju config dex-auth static-username=admin
   juju config dex-auth static-password=admin

Retrieve the dashboard IP address:

.. code-block:: bash

   microk8s kubectl -n kubeflow get svc istio-ingressgateway-workload -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

You should see something like the following:

.. code-block:: none

   10.64.140.43

Navigate to the IP address in your browser. 
Use the credentials previously set.

Once logged in, you should see the Kubeflow welcome page. 
Click ``Start Setup``, create a namespace for your work, and finally click ``Finish`` to continue to the dashboard.

You will see a ``Feast`` tab in the left-hand sidebar. 
It provides access to the Charmed Feast User Interface directly from the Kubeflow dashboard.