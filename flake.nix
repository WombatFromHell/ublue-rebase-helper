{
  description = "Bitwise-deterministic reproducible builds for ublue-rebase-helper";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    pyproject-nix,
    uv2nix,
    pyproject-build-systems,
  }: let
    # Read version from pyproject.toml as source of truth
    version = let
      content = builtins.readFile ./pyproject.toml;
      lines = builtins.split "\n" content;
      filtered = builtins.filter (line: builtins.isString line && (builtins.substring 0 9 line) == "version =") lines;
      match = builtins.match ".*version = \"([^\"]+)\".*" (builtins.head filtered);
    in
      if match != null
      then builtins.head match
      else throw "Version not found in pyproject.toml";

    # Use epoch 1 for maximum determinism (Jan 1, 1970)
    epoch = 1;

    forAllSystems = nixpkgs.lib.genAttrs ["x86_64-linux" "aarch64-linux"];

    # Read Python version from .python-version
    pyVerRaw = builtins.replaceStrings ["\n"] [""] (builtins.readFile ./.python-version);
    pyVerAttr = "python" + builtins.replaceStrings ["."] [""] pyVerRaw;

    mkPkgs = system: import nixpkgs {inherit system;};
    python = pkgs: pkgs.${pyVerAttr};

    # Load workspace from uv.lock and create overlay for reproducible Python packages
    workspace = uv2nix.lib.workspace.loadWorkspace {
      workspaceRoot = ./.;
    };
    projectOverlay = workspace.mkPyprojectOverlay {
      sourcePreference = "wheel";
    };

    mkPythonSet = system: let
      pkgs' = mkPkgs system;
    in
      (pkgs'.callPackage pyproject-nix.build.packages {
        python = python pkgs';
      }).overrideScope (nixpkgs.lib.composeManyExtensions [
        pyproject-build-systems.overlays.wheel
        projectOverlay
      ]);

    mkZipapp = system: let
      pkgs = mkPkgs system;
      py = python pkgs;
      pythonSet = mkPythonSet system;
      venv = pythonSet.mkVirtualEnv "urh-env" [];

      # Step A: Prepare source with version injection
      src = pkgs.stdenvNoCC.mkDerivation {
        name = "ublue-rebase-helper-src";
        buildInputs = [pkgs.gnused];
        phases = ["installPhase"];
        installPhase = ''
          mkdir -p $out
          cp -r ${./src} staging
          chmod -R u+w staging
          sed -i 's/^__version__ = .*/__version__ = "${version}"/' \
            "staging/urh/constants.py"
          cp -r staging/* $out/
        '';
      };
    in
      pkgs.stdenvNoCC.mkDerivation {
        name = "urh.pyz";

        nativeBuildInputs = with pkgs; [
          coreutils
          findutils
          gnused
          zip
          python3
          uv
        ];

        PYTHON = "${py}/bin/python3";

        buildPhase = ''
          mkdir -m 755 staging
          cp -r ${src}/* staging/

          # Ensure staging directory and all contents are writable before creating files
          chmod -R u+w staging

          # Create __main__.py entry point
          echo "from entry import main; main()" > staging/__main__.py

          # Normalize permissions and timestamps for determinism
          chmod -R u+w staging
          find staging -exec touch -d "@${builtins.toString epoch}" {} +

          # Build deterministic zip: sorted file list, no extra attributes (-X)
          (cd staging && find . \( -type d -o -type f \) | LC_ALL=C sort | zip -X -q -@ archive.zip)

          # Prepend shebang to create executable pyz
          echo '#!/usr/bin/env python3' > $out
          cat staging/archive.zip >> $out
          chmod +x $out
        '';

        dontUnpack = true;
        dontInstall = true;
      };
  in {
    packages = forAllSystems (system: {
      default = mkZipapp system;
    });

    devShells = forAllSystems (system: let
      pkgs = mkPkgs system;
      pythonSet = mkPythonSet system;
      venv = pythonSet.mkVirtualEnv "ublue-rebase-helper-dev" [];
    in
      pkgs.mkShell {
        name = "ublue-rebase-helper";

        packages = with pkgs;
          [
            bashInteractive
            coreutils
            findutils
            ripgrep
            jq
            less
            prettier
            rsync
            util-linux
            uv
            which
            zip
          ]
          ++ [
            # Drop-in replacement for `uv run` — deterministic venv from uv2nix
            venv
          ];

        shellHook = ''
          export PYTHONPATH="${venv}":$PYTHONPATH

          echo "ublue-rebase-helper development environment loaded"
          echo "Python: $(${python pkgs}/bin/python3 --version)"
          echo ""
          echo "Build with: make build  (local)"
          echo "Nix build: nix build    (reproducible)"
        '';

        VIRTUAL_ENV = "${venv}";
        PATH = "${venv}/bin:$PATH";
      });
  };
}
