{
  description = "Bitwise-deterministic reproducible builds for ublue-rebase-helper";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # Read Python version from .python-version file (strip newline and dot)
        pythonVersion = builtins.replaceStrings [ "\n" ] [ "" ] (builtins.readFile ./.python-version);
        pythonAttr = builtins.replaceStrings [ "." ] [ "" ] pythonVersion;
        python = pkgs."python${pythonAttr}";
      in
      {
        devShells.default = pkgs.mkShell {
          name = "urh";

          packages = [
            python
            pkgs.gnumake
            pkgs.zip # Needed for deterministic zipping
            pkgs.coreutils # For 'touch' and 'date'
            pkgs.jq # For JSON parsing in Makefile
          ];
          shellHook = ''
            export PYTHON=${python}/bin/python3

            echo "ProtonFetcher development environment loaded"
            echo "Python: $(python --version)"
            echo ""
            echo "Build with: make build"
            echo "The Makefile sets SOURCE_DATE_EPOCH for reproducible builds"
          '';
        };
      }
    );
}
