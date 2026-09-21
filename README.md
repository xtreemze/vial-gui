### vial-gui

# Docs and getting started

### Please visit [get.vial.today](https://get.vial.today/) to get started with Vial

Vial is an open-source cross-platform (Windows, Linux and Mac) GUI and a QMK fork for configuring your keyboard in real time.


![](https://get.vial.today/img/vial-win-1.png)


---


#### Releases

Visit https://get.vial.today/ to download a binary release of Vial.

#### Development

Python 3.6 is recommended (3.6 is the latest version that is officially supported by `fbs`).

Install dependencies:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

To launch the application afterwards:

```
source venv/bin/activate
fbs run
```

#### Architecture migration

The current Python/PyQt application remains the compatibility baseline while the xtreemze fork converges on a shared web/desktop configurator architecture. See [the desktop convergence plan](docs/DESKTOP_CONVERGENCE.md) and [migration parity matrix](docs/MIGRATION_PARITY.md). The active Halcyon editor work in PR #6 remains part of the reference behavior during this transition.
