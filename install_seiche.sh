mkdir -p $HOME/.local/bin
export PATH="$PATH:$HOME/.local/bin"
echo ""
echo "> ./install_seiche.sh"
echo "|--------------------------------------------------------|"
echo "|                                                        |"
echo "| Installing uv to ~/.local/bin ...                      |"
echo "|                                                        |"
echo "|--------------------------------------------------------|"
curl -LsSf https://astral.sh/uv/install.sh | sh
echo ""
echo "> ./install_seiche.sh"
echo "|--------------------------------------------------------|"
echo "|                                                        |"
echo "| Installing just to ~/.local/bin ...                    |"
echo "|                                                        |"
echo "|--------------------------------------------------------|"
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to $HOME/.local/bin
echo ""
echo "> ./install_seiche.sh"
echo "|--------------------------------------------------------|"
echo "|                                                        |"
echo "| Installing OpenTelemac Python API to ~/.local/bin ...  |"
echo "|                                                        |"
echo "|--------------------------------------------------------|"
just download --opentelemac --unzip $HOME/.local/bin
# add paths to .*rc files
for rc_file in $HOME/.bashrc $HOME/.zshrc; do
  if [ -f "$rc_file" ]; then
    if ! grep -q "SEICHE_OPENTELEMAC_PATH" "$rc_file"; then
      echo 'export PATH="$PATH:$HOME/.local/bin"' >> "$rc_file"
      echo 'export SEICHE_OPENTELEMAC_PATH="$HOME/.local/bin/opentelemac_python3_20240430"' >> "$rc_file"
    fi
    # source it now
    source "$rc_file"
  fi
done
echo ""
echo "> ./install_seiche.sh"
echo "|--------------------------------------------------------|"
echo "|                                                        |"
echo "| Everything is installed!                               |"
echo "| Thank you for using SEICHE :)                          |"
echo "|                                                        |"
echo "| You should restart your terminal before running SEICHE |"
echo "| to ensure the environment variables are correctly set. |"
echo "|                                                        |"
echo "|--------------------------------------------------------|"