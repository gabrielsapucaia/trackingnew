"""
Script para treinar modelo de Machine Learning com dados rotulados.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import StandardScaler
from scipy.signal import find_peaks
import os
import pickle
from datetime import datetime

# Caminhos dos arquivos
DATA_FILE = 'amostra/telemetria_20251212_20251213.csv'
LABELS_FILE = 'amostra/rotulos_carregamento.csv'
MODEL_FILE = 'amostra/modelo_carregamento.pkl'
SCALER_FILE = 'amostra/scaler_carregamento.pkl'
REPORT_FILE = 'amostra/relatorio_ml_carregamento.txt'

def load_data():
    """Carrega dados de telemetria."""
    df = pd.read_csv(DATA_FILE)
    df['time'] = pd.to_datetime(df['time'])
    df['speed_kmh'] = df['speed_kmh'].astype(float)
    df['linear_accel_magnitude'] = df['linear_accel_magnitude'].astype(float)
    return df

def load_labels():
    """Carrega rótulos."""
    if not os.path.exists(LABELS_FILE):
        print(f"Arquivo de rótulos não encontrado: {LABELS_FILE}")
        return None
    labels_df = pd.read_csv(LABELS_FILE)
    labels_df['start_time'] = pd.to_datetime(labels_df['start_time'])
    labels_df['end_time'] = pd.to_datetime(labels_df['end_time'])
    return labels_df

def extract_features(period_data, duration_minutes):
    """Extrai features de um período de parada."""
    vibration = period_data['linear_accel_magnitude'].values
    
    # Ajustar parâmetros baseado na duração
    if duration_minutes < 5:
        height_threshold = np.mean(vibration) + 0.3 * np.std(vibration)
        min_distance = len(vibration) // 15
        prominence = 0.005
    else:
        height_threshold = np.mean(vibration) + 0.25 * np.std(vibration)
        min_distance = len(vibration) // 25
        prominence = 0.004
    
    # Detectar picos
    peaks, properties = find_peaks(vibration,
                                 height=height_threshold,
                                 distance=min_distance,
                                 prominence=prominence,
                                 width=1)
    
    # Features básicas
    features = {
        'mean_vibration': np.mean(vibration),
        'std_vibration': np.std(vibration),
        'max_vibration': np.max(vibration),
        'min_vibration': np.min(vibration),
        'range_vibration': np.max(vibration) - np.min(vibration),
        'duration_minutes': duration_minutes,
        'num_peaks': len(peaks),
        'peaks_per_minute': len(peaks) / duration_minutes if duration_minutes > 0 else 0,
    }
    
    if len(peaks) >= 2:
        peak_heights = properties['peak_heights']
        peak_intervals = np.diff(peaks)
        
        features.update({
            'avg_peak_height': np.mean(peak_heights),
            'std_peak_height': np.std(peak_heights),
            'peak_variability': np.std(peak_heights) / np.mean(peak_heights) if np.mean(peak_heights) > 0 else 0,
            'avg_peak_interval': np.mean(peak_intervals),
            'std_peak_interval': np.std(peak_intervals),
            'regularity_score': 1 / (1 + np.std(peak_intervals) / np.mean(peak_intervals)) if np.mean(peak_intervals) > 0 else 0,
            'min_interval': np.min(peak_intervals),
            'max_interval': np.max(peak_intervals),
        })
        
        # Distribuição temporal dos picos
        peak_positions = peaks / len(vibration)
        features['peak_distribution'] = np.std(peak_positions)
        
        # Coeficiente de variação dos intervalos
        features['interval_cv'] = np.std(peak_intervals) / np.mean(peak_intervals) if np.mean(peak_intervals) > 0 else 999
    else:
        features.update({
            'avg_peak_height': 0,
            'std_peak_height': 0,
            'peak_variability': 0,
            'avg_peak_interval': 0,
            'std_peak_interval': 0,
            'regularity_score': 0,
            'min_interval': 0,
            'max_interval': 0,
            'peak_distribution': 0,
            'interval_cv': 999,
        })
    
    # Análise de atividade (burst detection)
    rolling_std = pd.Series(vibration).rolling(window=max(1, len(vibration)//10)).std()
    high_activity_periods = (rolling_std > np.mean(rolling_std) + np.std(rolling_std)).sum()
    features['high_activity_periods'] = high_activity_periods
    features['activity_ratio'] = high_activity_periods / len(vibration) if len(vibration) > 0 else 0
    
    return features

def prepare_training_data(df, labels_df):
    """Prepara dados de treinamento a partir dos rótulos."""
    X = []
    y = []
    period_ids = []
    
    print(f"Processando {len(labels_df)} períodos rotulados...")
    
    for idx, label_row in labels_df.iterrows():
        period_id = label_row['period_id']
        start_time = label_row['start_time']
        end_time = label_row['end_time']
        duration_minutes = label_row['duration_minutes']
        label = label_row['label']
        
        # Extrair dados do período
        period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] < 1.0)]
        
        if len(period_data) > 5:
            features = extract_features(period_data, duration_minutes)
            X.append(features)
            y.append(1 if label == 'Carregamento' else 0)
            period_ids.append(period_id)
    
    if len(X) == 0:
        print("Nenhum dado válido para treinamento!")
        return None, None, None
    
    # Converter para DataFrame
    X_df = pd.DataFrame(X)
    y_array = np.array(y)
    
    print(f"Dados preparados: {len(X_df)} amostras, {len(X_df.columns)} features")
    return X_df, y_array, period_ids

def train_model(X, y, test_size=0.2, random_state=42):
    """Treina modelo Random Forest."""
    # Dividir dados
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    print(f"\nDivisão dos dados:")
    print(f"  Treinamento: {len(X_train)} amostras")
    print(f"  Teste: {len(X_test)} amostras")
    
    # Normalizar features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Treinar modelo
    print("\nTreinando modelo Random Forest...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=random_state,
        class_weight='balanced'
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Avaliar
    train_score = model.score(X_train_scaled, y_train)
    test_score = model.score(X_test_scaled, y_test)
    
    print(f"\nAcurácia:")
    print(f"  Treinamento: {train_score:.3f}")
    print(f"  Teste: {test_score:.3f}")
    
    # Validação cruzada
    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)
    print(f"\nValidação Cruzada (5-fold):")
    print(f"  Média: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")
    
    # Predições no conjunto de teste
    y_pred = model.predict(X_test_scaled)
    
    print("\nRelatório de Classificação:")
    print(classification_report(y_test, y_pred, target_names=['Não Carregamento', 'Carregamento']))
    
    print("\nMatriz de Confusão:")
    print(confusion_matrix(y_test, y_pred))
    
    # Importância das features
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Features Mais Importantes:")
    print(feature_importance.head(10).to_string(index=False))
    
    return model, scaler, {
        'train_score': train_score,
        'test_score': test_score,
        'cv_mean': cv_scores.mean(),
        'cv_std': cv_scores.std(),
        'classification_report': classification_report(y_test, y_pred, target_names=['Não Carregamento', 'Carregamento']),
        'confusion_matrix': confusion_matrix(y_test, y_pred),
        'feature_importance': feature_importance
    }

def save_model(model, scaler, metrics):
    """Salva modelo e scaler."""
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(model, f)
    print(f"\nModelo salvo em: {MODEL_FILE}")
    
    with open(SCALER_FILE, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"Scaler salvo em: {SCALER_FILE}")
    
    # Salvar relatório
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE TREINAMENTO DO MODELO DE CARREGAMENTO\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("MÉTRICAS:\n")
        f.write(f"  Acurácia Treinamento: {metrics['train_score']:.3f}\n")
        f.write(f"  Acurácia Teste: {metrics['test_score']:.3f}\n")
        f.write(f"  Validação Cruzada: {metrics['cv_mean']:.3f} (+/- {metrics['cv_std']:.3f})\n\n")
        f.write("RELATÓRIO DE CLASSIFICAÇÃO:\n")
        f.write(metrics['classification_report'])
        f.write("\n\nMATRIZ DE CONFUSÃO:\n")
        f.write(str(metrics['confusion_matrix']))
        f.write("\n\nFEATURES MAIS IMPORTANTES:\n")
        f.write(metrics['feature_importance'].head(15).to_string(index=False))
    
    print(f"Relatório salvo em: {REPORT_FILE}")

def main():
    """Função principal."""
    print("=" * 60)
    print("TREINAMENTO DE MODELO DE MACHINE LEARNING")
    print("=" * 60)
    
    # Carregar dados
    print("\n1. Carregando dados...")
    df = load_data()
    print(f"   Dados de telemetria: {len(df)} registros")
    
    labels_df = load_labels()
    if labels_df is None:
        print("\nErro: Nenhum rótulo encontrado!")
        print("Por favor, rotule alguns períodos usando app_labeling.py primeiro.")
        return
    
    print(f"   Rótulos carregados: {len(labels_df)} períodos")
    
    # Verificar distribuição de rótulos
    label_counts = labels_df['label'].value_counts()
    print(f"\n   Distribuição de rótulos:")
    for label, count in label_counts.items():
        print(f"     {label}: {count}")
    
    if len(label_counts) < 2:
        print("\nErro: É necessário ter pelo menos 2 classes diferentes para treinar o modelo!")
        print("Por favor, rotule períodos de ambas as classes (Carregamento e Não Carregamento).")
        return
    
    # Preparar dados de treinamento
    print("\n2. Preparando dados de treinamento...")
    X, y, period_ids = prepare_training_data(df, labels_df)
    
    if X is None:
        return
    
    # Treinar modelo
    print("\n3. Treinando modelo...")
    model, scaler, metrics = train_model(X, y)
    
    # Salvar modelo
    print("\n4. Salvando modelo...")
    save_model(model, scaler, metrics)
    
    print("\n" + "=" * 60)
    print("TREINAMENTO CONCLUÍDO COM SUCESSO!")
    print("=" * 60)
    print(f"\nModelo salvo em: {MODEL_FILE}")
    print(f"Scaler salvo em: {SCALER_FILE}")
    print(f"Relatório salvo em: {REPORT_FILE}")

if __name__ == "__main__":
    main()
