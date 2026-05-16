{
  description = "Havoc - autonomous 1/10 scale RC car";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    zephyr.url = "github:zephyrproject-rtos/zephyr/v4.4.0";
    zephyr.flake = false;

    zephyr-nix.url = "github:nix-community/zephyr-nix";
    zephyr-nix.inputs.nixpkgs.follows = "nixpkgs";
    zephyr-nix.inputs.zephyr.follows = "zephyr";
  };

  outputs = { self, nixpkgs, zephyr-nix, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      zephyr = zephyr-nix.packages.${system};
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          (zephyr.sdk.override { targets = [ "arm-zephyr-eabi" ]; })
          zephyr.pythonEnv
          zephyr.hosttools-nix

          pkgs.cmake
          pkgs.ninja
          pkgs.dtc
          pkgs.gperf

          pkgs.just
        ];

        shellHook = ''
          echo "havoc dev shell - Zephyr v4.4.0 (arm-zephyr-eabi + native_sim)"
        '';
      };
    };
}
